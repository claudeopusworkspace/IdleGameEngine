from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from idleengine._types import compare

if TYPE_CHECKING:
    from idleengine.state import GameState


@dataclass
class SimulationContext:
    """Extra context available to terminal conditions during simulation."""

    last_purchase_time: float = 0.0
    stall_detected: bool = False
    total_purchases: int = 0


class TerminalCondition(ABC):
    """Base class for simulation stopping conditions."""

    @abstractmethod
    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool: ...

    @abstractmethod
    def describe(self) -> str: ...


class _TimeTerminal(TerminalCondition):
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds

    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool:
        return state.time_elapsed >= self.seconds

    def describe(self) -> str:
        return f"time({self.seconds})"


class _MilestoneTerminal(TerminalCondition):
    def __init__(self, milestone_id: str) -> None:
        self.milestone_id = milestone_id

    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool:
        return state.has_milestone(self.milestone_id)

    def describe(self) -> str:
        return f'milestone("{self.milestone_id}")'


class _CurrencyTerminal(TerminalCondition):
    def __init__(self, currency_id: str, op: str, threshold: float) -> None:
        self.currency_id = currency_id
        self.op = op
        self.threshold = threshold

    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool:
        return compare(state.currency_value(self.currency_id), self.op, self.threshold)

    def describe(self) -> str:
        return f'currency("{self.currency_id}", "{self.op}", {self.threshold})'


class _AllPurchasedTerminal(TerminalCondition):
    def __init__(self, tags: set[str] | None = None, element_ids: list[str] | None = None) -> None:
        self.tags = tags
        self.element_ids = element_ids

    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool:
        if self.element_ids:
            return all(state.element_count(eid) >= 1 for eid in self.element_ids)
        # If tags specified, we can't check without definition — rely on context
        # For simplicity, check all elements in state that we know about
        return False

    def describe(self) -> str:
        if self.element_ids:
            return f"all_purchased({self.element_ids})"
        return f"all_purchased(tags={self.tags})"


class _StallTerminal(TerminalCondition):
    def __init__(self, max_idle_seconds: float) -> None:
        self.max_idle_seconds = max_idle_seconds

    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool:
        if context is None:
            return False
        if context.stall_detected:
            return True
        gap = state.time_elapsed - context.last_purchase_time
        return gap >= self.max_idle_seconds

    def describe(self) -> str:
        return f"stall({self.max_idle_seconds})"


class _AnyTerminal(TerminalCondition):
    def __init__(self, conditions: list[TerminalCondition]) -> None:
        self.conditions = conditions

    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool:
        return any(c.is_met(state, context) for c in self.conditions)

    def describe(self) -> str:
        return " OR ".join(c.describe() for c in self.conditions)


class _AllTerminal(TerminalCondition):
    def __init__(self, conditions: list[TerminalCondition]) -> None:
        self.conditions = conditions

    def is_met(self, state: GameState, context: SimulationContext | None = None) -> bool:
        return all(c.is_met(state, context) for c in self.conditions)

    def describe(self) -> str:
        return " AND ".join(c.describe() for c in self.conditions)


class Terminal:
    """Factory for built-in terminal conditions."""

    @staticmethod
    def time(seconds: float) -> TerminalCondition:
        return _TimeTerminal(seconds)

    @staticmethod
    def milestone(milestone_id: str) -> TerminalCondition:
        return _MilestoneTerminal(milestone_id)

    @staticmethod
    def currency(currency_id: str, op: str, threshold: float) -> TerminalCondition:
        return _CurrencyTerminal(currency_id, op, threshold)

    @staticmethod
    def all_purchased(
        tags: set[str] | None = None,
        element_ids: list[str] | None = None,
    ) -> TerminalCondition:
        return _AllPurchasedTerminal(tags, element_ids)

    @staticmethod
    def stall(max_idle_seconds: float = 600) -> TerminalCondition:
        return _StallTerminal(max_idle_seconds)

    @staticmethod
    def any(*conditions: TerminalCondition) -> TerminalCondition:
        return _AnyTerminal(list(conditions))

    @staticmethod
    def all(*conditions: TerminalCondition) -> TerminalCondition:
        return _AllTerminal(list(conditions))
