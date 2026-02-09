from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from idleengine._types import DynamicStr
from idleengine.cost_scaling import CostScaling
from idleengine.effect import EffectDef
from idleengine.requirement import Requirement

if TYPE_CHECKING:
    from idleengine.state import GameState


@dataclass
class ElementDef:
    """Static definition of a purchasable game element."""

    id: str
    display_name: str = ""
    description: DynamicStr = ""
    base_cost: dict[str, float] = field(default_factory=dict)
    cost_scaling: CostScaling = field(default_factory=CostScaling.fixed)
    max_count: int | None = None
    effects: list[EffectDef] = field(default_factory=list)
    requirements: list[Requirement] = field(default_factory=list)
    purchase_requirements: list[Requirement] = field(default_factory=list)
    on_purchase: Callable[[GameState], None] | None = None
    tags: set[str] = field(default_factory=set)
    category: str = ""

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.id


@dataclass
class ElementState:
    """Mutable runtime state for an element."""

    count: int = 0
    available: bool = False
    affordable: bool = False
    unlocked: bool = False


@dataclass(frozen=True)
class ElementStatus:
    """Read-only snapshot of element state for query results."""

    id: str
    display_name: str
    count: int
    available: bool
    affordable: bool
    current_cost: dict[str, float]
    max_count: int | None
    category: str
    tags: frozenset[str]
