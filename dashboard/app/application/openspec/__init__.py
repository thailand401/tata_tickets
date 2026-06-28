"""OpenSpec document builders (Phase 3).

Pure, deterministic renderers that turn a structured Tech Spec (the validated
output of Phase 2) into a standard OpenSpec change bundle: proposal,
requirements, tasks, architecture, migration and checklist documents.

Everything here is *documentation only* — never source code. The migration
artifact is a suggested DDL document, not an executed script.
"""

from __future__ import annotations

from app.application.openspec.builder import build_bundle, build_tasks

__all__ = ["build_bundle", "build_tasks"]
