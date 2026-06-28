"""Tech Spec service: free-text ticket -> AI analysis -> structured spec.

The output is documentation only (never source code). Generation is versioned
(full history), uses a versioned prompt template, retries on transient LLM
failures, and supports comparing any two generated versions.
"""

from __future__ import annotations

import json
from typing import Any

from app.application.rbac import rbac
from app.application.recorder import record_audit, record_event
from app.application.retry import with_retry
from app.application.services.base import CrudService
from app.core.exceptions import GenerationError, NotFoundError, ValidationError
from app.domain.entities import TechSpecContent
from app.domain.enums import AuditAction, GenerationStatus, SpecStatus
from app.domain.llm import LLMClient, LLMError, LLMMessage, LLMRequest
from app.domain.repositories import Repository
from app.infrastructure.llm import get_llm_client
from app.infrastructure.supabase.client import get_service_client
from app.infrastructure.supabase.repository import SupabaseRepository

#: System prompt used when a spec has no versioned prompt bound. Producing this
#: via the prompt library makes it fully versionable (see ``prompt_id``).
DEFAULT_SPEC_PROMPT = (
    "You are a senior technical analyst. Analyze the free-text ticket and "
    "produce a STANDARD TECH SPEC as documentation only. Do NOT write any "
    "source code. Respond with a single JSON object using exactly these keys: "
    "feature (string), business_goal (string), functional_requirements "
    "(string[]), non_functional (string[]), api (string[]), database "
    "(string[]), acceptance_criteria (string[]), risks (string[]), "
    "dependencies (string[]), estimate (string), priority "
    "(one of: low, medium, high, critical). Return only the JSON object."
)

#: The structured fields compared between two versions.
_SPEC_FIELDS = tuple(TechSpecContent.model_fields.keys())


def _repo(table: str) -> SupabaseRepository:
    return SupabaseRepository(get_service_client(), table)


def _strip_code_fence(text: str) -> str:
    body = text.strip()
    if body.startswith("```"):
        # Drop the opening fence (``` or ```json) and the closing fence.
        body = body.split("\n", 1)[1] if "\n" in body else body
        if body.rstrip().endswith("```"):
            body = body.rstrip()[:-3]
    return body.strip()


def parse_spec_content(text: str) -> dict[str, Any]:
    """Parse and validate an LLM response into the Tech Spec contract."""
    try:
        data = json.loads(_strip_code_fence(text))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError("LLM response JSON must be an object")
    try:
        content = TechSpecContent.model_validate(data)
    except Exception as exc:  # pydantic ValidationError -> our ValidationError
        raise ValidationError(f"LLM response did not match spec contract: {exc}") from exc
    return content.model_dump(mode="json")


class TechSpecService(CrudService):
    resource = "spec"
    entity_type = "tech_spec"

    def __init__(
        self,
        repository: Repository | None = None,
        *,
        versions: Repository | None = None,
        prompts: Repository | None = None,
        prompt_versions: Repository | None = None,
        models: Repository | None = None,
        llm: LLMClient | None = None,
    ) -> None:
        super().__init__(repository or _repo("tech_specs"))
        self._versions = versions or _repo("tech_spec_versions")
        self._prompts = prompts or _repo("prompts")
        self._prompt_versions = prompt_versions or _repo("prompt_versions")
        self._models = models or _repo("models")
        self._llm = llm

    # -- history ------------------------------------------------------------
    def list_versions(self, actor_id: str, spec_id: str) -> list[dict[str, Any]]:
        rbac.require(actor_id, "spec:read")
        return self._versions.list(
            filters={"spec_id": spec_id},
            order_by="version",
            descending=True,
            limit=200,
        )

    def get_version(self, actor_id: str, spec_id: str, version: int) -> dict[str, Any]:
        rbac.require(actor_id, "spec:read")
        row = self._versions.find_one({"spec_id": spec_id, "version": version})
        if not row:
            raise NotFoundError(f"spec version {version} not found")
        return row

    # -- compare ------------------------------------------------------------
    def compare(
        self, actor_id: str, spec_id: str, version_a: int, version_b: int
    ) -> dict[str, Any]:
        """Field-by-field diff between two generated versions."""
        rbac.require(actor_id, "spec:read")
        a = self._versions.find_one({"spec_id": spec_id, "version": version_a})
        b = self._versions.find_one({"spec_id": spec_id, "version": version_b})
        if not a:
            raise NotFoundError(f"spec version {version_a} not found")
        if not b:
            raise NotFoundError(f"spec version {version_b} not found")

        content_a = a.get("content") or {}
        content_b = b.get("content") or {}
        diff: dict[str, Any] = {}
        for field in _SPEC_FIELDS:
            va = content_a.get(field)
            vb = content_b.get(field)
            diff[field] = {"a": va, "b": vb, "changed": va != vb}

        return {
            "spec_id": spec_id,
            "a": {"version": version_a, "status": a.get("status"), "content": content_a},
            "b": {"version": version_b, "status": b.get("status"), "content": content_b},
            "diff": diff,
        }

    # -- generation ---------------------------------------------------------
    def generate(
        self,
        actor_id: str,
        spec_id: str,
        *,
        model_id: str | None = None,
        prompt_id: str | None = None,
        temperature: float = 0.2,
        max_attempts: int = 3,
        notes: str | None = None,
        workspace_id: str | None = None,
    ) -> dict[str, Any]:
        """Run AI analysis and store the result as a new immutable version.

        Calling this again re-generates (a fresh version) — that is the
        user-facing retry. Transient LLM failures are retried internally up to
        ``max_attempts`` times before a version is recorded as failed.
        """
        rbac.require(actor_id, "spec:generate", workspace_id)
        spec = self.repo.get(spec_id)
        if not spec:
            raise NotFoundError("tech spec not found")
        source_text = (spec.get("source_text") or "").strip()
        if not source_text:
            raise ValidationError("Tech spec source_text is empty")

        self.repo.update(spec_id, {"status": SpecStatus.GENERATING.value})

        system_prompt, used_prompt_id, used_prompt_version = self._resolve_prompt(
            prompt_id or spec.get("prompt_id")
        )
        provider, model_key, used_model_id = self._resolve_model(
            model_id or spec.get("model_id")
        )

        request = LLMRequest(
            messages=[
                LLMMessage(role="system", content=system_prompt),
                LLMMessage(role="user", content=source_text),
            ],
            model_key=model_key or "",
            temperature=temperature,
        )
        client = self._llm or get_llm_client(provider)
        next_version = int(spec.get("current_version", 0)) + 1

        def _attempt() -> tuple[str, dict[str, Any]]:
            response = client.complete(request)
            content = parse_spec_content(response.text)
            return response.text, content

        try:
            result = with_retry(
                _attempt,
                attempts=max_attempts,
                exceptions=(LLMError, ValidationError, json.JSONDecodeError),
            )
            raw_output, content = result.value  # type: ignore[misc]
            version_row = self._record_version(
                spec_id=spec_id,
                version=next_version,
                status=GenerationStatus.SUCCEEDED,
                content=content,
                raw_output=raw_output,
                provider=provider,
                model_key=model_key,
                model_id=used_model_id,
                prompt_id=used_prompt_id,
                prompt_version=used_prompt_version,
                attempts=result.attempts,
                error=None,
                notes=notes,
                actor_id=actor_id,
            )
            self.repo.update(
                spec_id,
                {"current_version": next_version, "status": SpecStatus.READY.value},
            )
            self._emit(actor_id, spec_id, version_row, workspace_id, succeeded=True)
            return version_row
        except Exception as exc:
            version_row = self._record_version(
                spec_id=spec_id,
                version=next_version,
                status=GenerationStatus.FAILED,
                content={},
                raw_output=None,
                provider=provider,
                model_key=model_key,
                model_id=used_model_id,
                prompt_id=used_prompt_id,
                prompt_version=used_prompt_version,
                attempts=max_attempts,
                error=str(exc),
                notes=notes,
                actor_id=actor_id,
            )
            self.repo.update(
                spec_id,
                {"current_version": next_version, "status": SpecStatus.FAILED.value},
            )
            self._emit(actor_id, spec_id, version_row, workspace_id, succeeded=False)
            raise GenerationError(f"Tech spec generation failed: {exc}") from exc

    # -- helpers ------------------------------------------------------------
    def _resolve_prompt(
        self, prompt_id: str | None
    ) -> tuple[str, str | None, int | None]:
        if prompt_id:
            prompt = self._prompts.get(prompt_id)
            if prompt:
                version = self._prompt_versions.find_one(
                    {"prompt_id": prompt_id, "version": prompt.get("current_version")}
                )
                if version and (version.get("content") or "").strip():
                    return version["content"], prompt_id, version.get("version")
        return DEFAULT_SPEC_PROMPT, prompt_id, None

    def _resolve_model(
        self, model_id: str | None
    ) -> tuple[str | None, str, str | None]:
        if model_id:
            model = self._models.get(model_id)
            if model:
                return model.get("provider"), model.get("model_key", ""), model_id
        # Dynamic selection: first active model, else fall back to the offline stub.
        actives = self._models.list(filters={"status": "active"}, limit=1)
        if actives:
            model = actives[0]
            return model.get("provider"), model.get("model_key", ""), model.get("id")
        return None, "", None

    def _record_version(
        self,
        *,
        spec_id: str,
        version: int,
        status: GenerationStatus,
        content: dict[str, Any],
        raw_output: str | None,
        provider: str | None,
        model_key: str,
        model_id: str | None,
        prompt_id: str | None,
        prompt_version: int | None,
        attempts: int,
        error: str | None,
        notes: str | None,
        actor_id: str,
    ) -> dict[str, Any]:
        return self._versions.create(
            {
                "spec_id": spec_id,
                "version": version,
                "status": status.value,
                "content": content,
                "raw_output": raw_output,
                "provider": provider,
                "model_key": model_key or None,
                "model_id": model_id,
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "attempts": attempts,
                "error": error,
                "notes": notes,
                "created_by": actor_id,
            }
        )

    def _emit(
        self,
        actor_id: str,
        spec_id: str,
        version_row: dict[str, Any],
        workspace_id: str | None,
        *,
        succeeded: bool,
    ) -> None:
        record_audit(
            actor_id=actor_id,
            action=AuditAction.GENERATE.value,
            entity_type="tech_spec_version",
            entity_id=str(version_row.get("id")),
            after=version_row,
        )
        record_event(
            event_type="tech_spec.generated" if succeeded else "tech_spec.failed",
            source="dashboard",
            workspace_id=workspace_id,
            payload={
                "spec_id": spec_id,
                "version": version_row.get("version"),
                "status": version_row.get("status"),
            },
        )
