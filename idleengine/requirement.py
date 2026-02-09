from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

from idleengine._types import compare

if TYPE_CHECKING:
    from idleengine.state import GameState


class Requirement(ABC):
    """Base class for all requirements — boolean conditions on game state."""

    @abstractmethod
    def evaluate(self, state: GameState) -> bool: ...

    def __and__(self, other: Requirement) -> Requirement:
        return _AllRequirement([self, other])

    def __or__(self, other: Requirement) -> Requirement:
        return _AnyRequirement([self, other])


# ── Private implementations ──────────────────────────────────────────


class _ResourceRequirement(Requirement):
    def __init__(self, currency_id: str, op: str, threshold: float) -> None:
        self.currency_id = currency_id
        self.op = op
        self.threshold = threshold

    def evaluate(self, state: GameState) -> bool:
        return compare(state.currency_value(self.currency_id), self.op, self.threshold)


class _TotalEarnedRequirement(Requirement):
    def __init__(self, currency_id: str, op: str, threshold: float) -> None:
        self.currency_id = currency_id
        self.op = op
        self.threshold = threshold

    def evaluate(self, state: GameState) -> bool:
        return compare(state.total_earned(self.currency_id), self.op, self.threshold)


class _OwnsRequirement(Requirement):
    def __init__(self, element_id: str) -> None:
        self.element_id = element_id

    def evaluate(self, state: GameState) -> bool:
        return state.element_count(self.element_id) >= 1


class _CountRequirement(Requirement):
    def __init__(self, element_id: str, op: str, threshold: int) -> None:
        self.element_id = element_id
        self.op = op
        self.threshold = threshold

    def evaluate(self, state: GameState) -> bool:
        return compare(state.element_count(self.element_id), self.op, self.threshold)


class _MilestoneRequirement(Requirement):
    def __init__(self, milestone_id: str) -> None:
        self.milestone_id = milestone_id

    def evaluate(self, state: GameState) -> bool:
        return state.has_milestone(self.milestone_id)


class _TimeRequirement(Requirement):
    def __init__(self, op: str, seconds: float) -> None:
        self.op = op
        self.seconds = seconds

    def evaluate(self, state: GameState) -> bool:
        return compare(state.time_elapsed, self.op, self.seconds)


class _AllRequirement(Requirement):
    def __init__(self, reqs: list[Requirement]) -> None:
        self.reqs = reqs

    def evaluate(self, state: GameState) -> bool:
        return all(r.evaluate(state) for r in self.reqs)


class _AnyRequirement(Requirement):
    def __init__(self, reqs: list[Requirement]) -> None:
        self.reqs = reqs

    def evaluate(self, state: GameState) -> bool:
        return any(r.evaluate(state) for r in self.reqs)


class _CustomRequirement(Requirement):
    def __init__(self, fn: Callable[[GameState], bool]) -> None:
        self.fn = fn

    def evaluate(self, state: GameState) -> bool:
        return self.fn(state)


class EstimatedTimeRequirement(Requirement):
    """Simulation-only requirement that samples from a time distribution."""

    def __init__(
        self,
        mean: float,
        variance: float = 0.0,
        description: str = "",
    ) -> None:
        self.mean = mean
        self.variance = variance
        self.description = description
        self._sampled_time: float | None = None
        self._rng: random.Random | None = None

    def inject_rng(self, rng: random.Random) -> None:
        self._rng = rng

    def sample(self, rng: random.Random | None = None) -> float:
        """Sample a concrete time from the distribution."""
        r = rng or self._rng or random.Random()
        if self.variance > 0:
            t = r.gauss(self.mean, self.variance)
            return max(0.0, t)
        return self.mean

    def reset(self) -> None:
        self._sampled_time = None

    def evaluate(self, state: GameState) -> bool:
        if self._sampled_time is None:
            self._sampled_time = self.sample()
        return state.time_elapsed >= self._sampled_time


# ── Public factory ───────────────────────────────────────────────────


class Req:
    """Factory for built-in requirement types."""

    @staticmethod
    def resource(currency_id: str, op: str, threshold: float) -> Requirement:
        return _ResourceRequirement(currency_id, op, threshold)

    @staticmethod
    def total_earned(currency_id: str, op: str, threshold: float) -> Requirement:
        return _TotalEarnedRequirement(currency_id, op, threshold)

    @staticmethod
    def owns(element_id: str) -> Requirement:
        return _OwnsRequirement(element_id)

    @staticmethod
    def count(element_id: str, op: str, threshold: int) -> Requirement:
        return _CountRequirement(element_id, op, threshold)

    @staticmethod
    def milestone(milestone_id: str) -> Requirement:
        return _MilestoneRequirement(milestone_id)

    @staticmethod
    def time(op: str, seconds: float) -> Requirement:
        return _TimeRequirement(op, seconds)

    @staticmethod
    def all(*reqs: Requirement) -> Requirement:
        return _AllRequirement(list(reqs))

    @staticmethod
    def any(*reqs: Requirement) -> Requirement:
        return _AnyRequirement(list(reqs))

    @staticmethod
    def custom(fn: Callable[[GameState], bool]) -> Requirement:
        return _CustomRequirement(fn)

    @staticmethod
    def estimated_time(
        mean: float,
        variance: float = 0.0,
        description: str = "",
    ) -> EstimatedTimeRequirement:
        return EstimatedTimeRequirement(mean, variance, description)
