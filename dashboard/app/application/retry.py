"""A small synchronous retry helper used by cross-cutting flows (e.g. LLM)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass
class RetryResult:
    """The outcome of a retried call: its value and how many attempts ran."""

    value: object
    attempts: int


def with_retry(
    fn: Callable[[], T],
    *,
    attempts: int = 3,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> RetryResult:
    """Call ``fn`` up to ``attempts`` times, retrying on ``exceptions``.

    Returns a :class:`RetryResult` carrying the value and the attempt count.
    Re-raises the last exception if every attempt fails.
    """
    if attempts < 1:
        raise ValueError("attempts must be >= 1")

    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return RetryResult(value=fn(), attempts=attempt)
        except exceptions as exc:  # noqa: PERF203
            last_exc = exc
            if on_retry is not None:
                on_retry(attempt, exc)
    assert last_exc is not None  # for type-checkers; loop ran at least once
    raise last_exc
