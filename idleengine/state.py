from __future__ import annotations

from typing import TYPE_CHECKING

from idleengine.currency import CurrencyState
from idleengine.element import ElementState

if TYPE_CHECKING:
    from idleengine.definition import GameDefinition


class GameState:
    """Mutable runtime container holding all game state."""

    def __init__(self, definition: GameDefinition) -> None:
        self.time_elapsed: float = 0.0
        self.currencies: dict[str, CurrencyState] = {}
        self.elements: dict[str, ElementState] = {}
        self.milestones_reached: dict[str, float] = {}
        self.prestige_counts: dict[str, int] = {}
        self.run_number: int = 1

        for cdef in definition.currencies:
            cs = CurrencyState(
                current=cdef.initial_value,
                total_earned=cdef.initial_value,
            )
            self.currencies[cdef.id] = cs

        for edef in definition.elements:
            self.elements[edef.id] = ElementState()

        for player in definition.prestige_layers:
            self.prestige_counts[player.id] = 0

    def currency_value(self, id: str) -> float:
        cs = self.currencies.get(id)
        return cs.current if cs else 0.0

    def currency_rate(self, id: str) -> float:
        cs = self.currencies.get(id)
        return cs.current_rate if cs else 0.0

    def element_count(self, id: str) -> int:
        es = self.elements.get(id)
        return es.count if es else 0

    def has_milestone(self, id: str) -> bool:
        return id in self.milestones_reached

    def total_earned(self, id: str) -> float:
        cs = self.currencies.get(id)
        return cs.total_earned if cs else 0.0
