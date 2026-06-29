"""Deterministic test-plan generators (Phase 8).

Pure functions: given an OpenSpec bundle's documents (the Phase 3 artifacts)
they return a structured test plan — suites of every kind (unit, integration,
api, regression, edge case, mock, benchmark), each with cases, plus coverage
targets, benchmark budgets and a rendered report. No I/O, no randomness, so the
whole phase is reproducible and testable offline. Documentation only — never
executable source code.
"""

from __future__ import annotations

from typing import Any

from app.domain.enums import TaskCategory, TestKind

# Suites are ordered the way the report renders them.
_KIND_ORDER = (
    TestKind.UNIT,
    TestKind.INTEGRATION,
    TestKind.API,
    TestKind.REGRESSION,
    TestKind.EDGE_CASE,
    TestKind.MOCK,
    TestKind.BENCHMARK,
)

#: Default framework hint per kind (advisory only).
_FRAMEWORK: dict[str, str] = {
    TestKind.UNIT.value: "pytest",
    TestKind.INTEGRATION.value: "pytest",
    TestKind.API.value: "pytest + httpx",
    TestKind.REGRESSION.value: "pytest",
    TestKind.EDGE_CASE.value: "pytest.mark.parametrize",
    TestKind.MOCK.value: "pytest fixtures / fakes",
    TestKind.BENCHMARK.value: "pytest-benchmark",
}


def _tasks(documents: dict[str, Any]) -> list[dict[str, Any]]:
    tasks = (documents.get("tasks") or {}).get("data", {}).get("tasks") or []
    return [t for t in tasks if isinstance(t, dict)]


def _by_category(tasks: list[dict[str, Any]], category: TaskCategory) -> list[dict]:
    return [t for t in tasks if t.get("category") == category.value]


def _case(name: str, given: str, when: str, then: str, kind: TestKind) -> dict[str, Any]:
    return {
        "name": name,
        "given": given,
        "when": when,
        "then": then,
        "kind": kind.value,
        "status": "planned",
    }


def _api_titles(tasks: list[dict[str, Any]]) -> list[str]:
    return [t["title"] for t in _by_category(tasks, TaskCategory.BACKEND)]


def _db_titles(tasks: list[dict[str, Any]]) -> list[str]:
    return [t["title"] for t in _by_category(tasks, TaskCategory.DATABASE)]


# ---------------------------------------------------------------------------
# Suite builders (one per TestKind)
# ---------------------------------------------------------------------------
def _unit_cases(tasks: list[dict[str, Any]]) -> list[dict]:
    impl = [
        t
        for t in tasks
        if t.get("category") in {TaskCategory.BACKEND.value, TaskCategory.FRONTEND.value}
    ]
    cases = [
        _case(
            f"test_{t['key'].lower()}_happy_path",
            f"a valid input for '{t['title']}'",
            "the unit under test is invoked",
            "it returns the expected result without side effects",
            TestKind.UNIT,
        )
        for t in impl
    ]
    return cases or [
        _case(
            "test_core_logic_happy_path",
            "a valid input",
            "the function runs",
            "it returns the expected output",
            TestKind.UNIT,
        )
    ]


def _integration_cases(tasks: list[dict[str, Any]]) -> list[dict]:
    cases: list[dict] = []
    for t in tasks:
        deps = t.get("depends_on") or []
        if deps:
            cases.append(
                _case(
                    f"test_{t['key'].lower()}_integrates_with_deps",
                    f"dependencies {', '.join(deps)} are in place",
                    f"'{t['title']}' executes end-to-end",
                    "the components cooperate and persist consistent state",
                    TestKind.INTEGRATION,
                )
            )
    return cases or [
        _case(
            "test_pipeline_end_to_end",
            "the full stack is wired",
            "a request flows through every layer",
            "the result is persisted and returned",
            TestKind.INTEGRATION,
        )
    ]


def _api_cases(tasks: list[dict[str, Any]]) -> list[dict]:
    endpoints = _api_titles(tasks)
    cases = [
        _case(
            f"test_endpoint_{i}_contract",
            "an authenticated request",
            f"calling '{ep}'",
            "status 2xx and the response matches the schema",
            TestKind.API,
        )
        for i, ep in enumerate(endpoints, 1)
    ]
    return cases or [
        _case(
            "test_endpoint_contract",
            "an authenticated request",
            "the endpoint is called",
            "status 2xx and the schema matches",
            TestKind.API,
        )
    ]


def _regression_cases(tasks: list[dict[str, Any]]) -> list[dict]:
    crit: list[str] = []
    for t in tasks:
        if t.get("category") == TaskCategory.TESTING.value and t.get("acceptance"):
            crit = [c.strip() for c in str(t["acceptance"]).split(";") if c.strip()]
    cases = [
        _case(
            f"test_regression_criterion_{i}",
            "a previously fixed scenario",
            f"verifying '{c}'",
            "behaviour is unchanged from the accepted baseline",
            TestKind.REGRESSION,
        )
        for i, c in enumerate(crit, 1)
    ]
    return cases or [
        _case(
            "test_regression_baseline",
            "the accepted baseline behaviour",
            "the feature is exercised again",
            "no acceptance criterion regresses",
            TestKind.REGRESSION,
        )
    ]


def _edge_cases(tasks: list[dict[str, Any]]) -> list[dict]:
    base = [
        ("empty input", "the input is empty/null", "returns a clear validation error"),
        ("boundary input", "values at min/max bounds", "handles limits without overflow"),
        ("invalid input", "malformed/unauthorized data", "rejects with 4xx, no leak"),
    ]
    return [
        _case(
            f"test_edge_{name.replace(' ', '_')}",
            given,
            "the system is invoked",
            then,
            TestKind.EDGE_CASE,
        )
        for name, given, then in base
    ]


def _mock_cases(tasks: list[dict[str, Any]]) -> tuple[list[dict], list[str]]:
    mocks = ["LLMClient", "TaskExecutor", "Repository (Supabase)"]
    if _api_titles(tasks):
        mocks.append("external HTTP services")
    if _db_titles(tasks):
        mocks.append("database transactions")
    cases = [
        _case(
            f"test_mock_{m.split()[0].lower()}",
            f"a fake/stub for {m}",
            "the unit under test runs offline",
            "no live dependency is contacted",
            TestKind.MOCK,
        )
        for m in mocks
    ]
    return cases, mocks


def _benchmark_cases(tasks: list[dict[str, Any]]) -> tuple[list[dict], list[dict]]:
    endpoints = _api_titles(tasks) or ["core operation"]
    budgets = [{"target": ep, "p95_ms": 200, "throughput_rps": 50} for ep in endpoints]
    cases = [
        _case(
            f"test_benchmark_{i}",
            "a warmed-up environment",
            f"load on '{b['target']}'",
            f"p95 < {b['p95_ms']}ms at >= {b['throughput_rps']} rps",
            TestKind.BENCHMARK,
        )
        for i, b in enumerate(budgets, 1)
    ]
    return cases, budgets


def build_suites(documents: dict[str, Any]) -> list[dict[str, Any]]:
    """Build every test suite (with cases) from OpenSpec documents."""
    tasks = _tasks(documents)
    mock_cases, mocks = _mock_cases(tasks)
    bench_cases, budgets = _benchmark_cases(tasks)
    cases_by_kind = {
        TestKind.UNIT: _unit_cases(tasks),
        TestKind.INTEGRATION: _integration_cases(tasks),
        TestKind.API: _api_cases(tasks),
        TestKind.REGRESSION: _regression_cases(tasks),
        TestKind.EDGE_CASE: _edge_cases(tasks),
        TestKind.MOCK: mock_cases,
        TestKind.BENCHMARK: bench_cases,
    }
    suites: list[dict[str, Any]] = []
    for kind in _KIND_ORDER:
        cases = cases_by_kind[kind]
        suites.append(
            {
                "kind": kind.value,
                "title": f"{kind.value.replace('_', ' ').title()} tests",
                "framework": _FRAMEWORK[kind.value],
                "summary": f"{len(cases)} planned case(s).",
                "mocks": mocks if kind is TestKind.MOCK else [],
                "data": {"budgets": budgets} if kind is TestKind.BENCHMARK else {},
                "cases": cases,
            }
        )
    return suites


def _render_report(
    title: str, suites: list[dict[str, Any]], coverage_target: int
) -> str:
    rows = "\n".join(
        f"| {s['title']} | {s['framework']} | {len(s['cases'])} |" for s in suites
    )
    total = sum(len(s["cases"]) for s in suites)
    return (
        f"# Test Report: {title}\n\n"
        "> Documentation only — a generated test plan, not executed results.\n\n"
        "## Summary\n\n"
        f"- **Suites:** {len(suites)}\n"
        f"- **Planned cases:** {total}\n"
        f"- **Coverage target:** {coverage_target}%\n\n"
        "## Suites\n\n"
        "| Suite | Framework | Cases |\n"
        "|-------|-----------|-------|\n"
        f"{rows}\n\n"
        "## Coverage\n\n"
        f"- [ ] Line coverage >= {coverage_target}%\n"
        f"- [ ] Branch coverage >= {coverage_target}%\n"
        "- [ ] No critical path untested\n\n"
        "## Gate\n\n"
        "- [ ] All suites green\n"
        "- [ ] Edge cases asserted\n"
        "- [ ] Benchmark budgets met\n"
    )


def build_test_plan(
    title: str, documents: dict[str, Any], *, coverage_target: int = 80
) -> dict[str, Any]:
    """Build a full test plan from OpenSpec documents.

    Returns ``{"suites": [...], "case_count", "report", "coverage_target"}``.
    """
    suites = build_suites(documents)
    return {
        "suites": suites,
        "suite_count": len(suites),
        "case_count": sum(len(s["cases"]) for s in suites),
        "coverage_target": coverage_target,
        "report": _render_report(title, suites, coverage_target),
    }
