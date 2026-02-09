from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from idleengine.requirement import Requirement

if TYPE_CHECKING:
    from idleengine.state import GameState


@dataclass
class PrestigeLayerDef:
    """Definition of a prestige (reset) layer."""

    id: str
    prestige_currency: str = ""
    reward_formula: Callable[[GameState], float] | None = None
    currencies_reset: list[str] | str = field(default_factory=list)
    elements_reset: list[str] | str = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    minimum_reward: float = 0.0


@dataclass(frozen=True)
class PrestigeResult:
    """Outcome of a prestige attempt."""

    success: bool
    reward_amount: float = 0.0
    currencies_reset: list[str] = field(default_factory=list)
    elements_reset: list[str] = field(default_factory=list)
    reason: str = ""
