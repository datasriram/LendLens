from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter


class TimingProfile:
    """Request-local wall-clock timings in seconds."""

    def __init__(self) -> None:
        self.started = perf_counter()
        self.seconds: dict[str, float] = {}

    def elapsed(self) -> float:
        return perf_counter() - self.started

    def fork(self, elapsed: float) -> TimingProfile:
        profile = TimingProfile()
        profile.started -= elapsed
        profile.seconds.update(self.seconds)
        return profile

    def finish(self) -> float:
        elapsed = self.elapsed()
        self.seconds["service_total"] = elapsed
        return round(elapsed, 3)

    def as_dict(self) -> dict[str, float]:
        return {stage: round(seconds, 3) for stage, seconds in self.seconds.items()}


@contextmanager
def measure(profile: TimingProfile | None, stage: str) -> Iterator[None]:
    if profile is None:
        yield
        return

    started = perf_counter()
    try:
        yield
    finally:
        elapsed = perf_counter() - started
        profile.seconds[stage] = profile.seconds.get(stage, 0.0) + elapsed
