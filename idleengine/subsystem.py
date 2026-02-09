from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from idleengine.state import GameState


class Subsystem(ABC):
    """Extension point for mechanics that don't fit currency/element model."""

    @abstractmethod
    def tick(self, state: GameState, delta: float) -> None: ...


class SimulationProxy(ABC):
    """Simplified model of a subsystem's behavior for simulation."""

    @abstractmethod
    def estimate_production(
        self, state: GameState, duration: float
    ) -> dict[str, float]: ...
