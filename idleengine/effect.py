from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Callable

from idleengine._types import DynamicFloat, resolve_value

if TYPE_CHECKING:
    from idleengine.state import GameState
    from idleengine.requirement import Requirement


class EffectType(Enum):
    PRODUCTION_FLAT = auto()
    PRODUCTION_ADD_PCT = auto()
    PRODUCTION_MULT = auto()
    GLOBAL_MULT = auto()
    CLICK_FLAT = auto()
    CLICK_MULT = auto()
    COST_MULT = auto()
    CAP_FLAT = auto()
    CAP_MULT = auto()
    AUTO_CLICK = auto()
    GRANT = auto()
    UNLOCK = auto()
    CUSTOM = auto()


class EffectPhase(Enum):
    BASE = auto()
    BONUS_ADD = auto()
    BONUS_MULT = auto()
    GLOBAL = auto()
    CLICK = auto()
    COST = auto()
    CAP = auto()
    AUTO = auto()
    IMMEDIATE = auto()
    CUSTOM = auto()


DEFAULT_PHASE: dict[EffectType, EffectPhase] = {
    EffectType.PRODUCTION_FLAT: EffectPhase.BASE,
    EffectType.PRODUCTION_ADD_PCT: EffectPhase.BONUS_ADD,
    EffectType.PRODUCTION_MULT: EffectPhase.BONUS_MULT,
    EffectType.GLOBAL_MULT: EffectPhase.GLOBAL,
    EffectType.CLICK_FLAT: EffectPhase.CLICK,
    EffectType.CLICK_MULT: EffectPhase.CLICK,
    EffectType.COST_MULT: EffectPhase.COST,
    EffectType.CAP_FLAT: EffectPhase.CAP,
    EffectType.CAP_MULT: EffectPhase.CAP,
    EffectType.AUTO_CLICK: EffectPhase.AUTO,
    EffectType.GRANT: EffectPhase.IMMEDIATE,
    EffectType.UNLOCK: EffectPhase.IMMEDIATE,
    EffectType.CUSTOM: EffectPhase.CUSTOM,
}


@dataclass
class EffectDef:
    """Definition of a single effect produced by an element."""

    type: EffectType
    target: str
    value: DynamicFloat = 0.0
    condition: Requirement | None = None
    phase: EffectPhase | None = None

    def __post_init__(self) -> None:
        if self.phase is None:
            self.phase = DEFAULT_PHASE.get(self.type, EffectPhase.CUSTOM)

    def resolve(self, state: GameState) -> float:
        return resolve_value(self.value, state)

    def is_active(self, state: GameState) -> bool:
        if self.condition is None:
            return True
        return self.condition.evaluate(state)


class Effect:
    """Convenience constructors for common effect patterns."""

    @staticmethod
    def per_count(
        element: str,
        type: EffectType,
        target: str,
        per_unit: float,
        condition: Requirement | None = None,
    ) -> EffectDef:
        """Value scales with owned count of *element*."""
        _element = element
        _per_unit = per_unit

        def _value(state: GameState) -> float:
            return state.element_count(_element) * _per_unit

        return EffectDef(type=type, target=target, value=_value, condition=condition)

    @staticmethod
    def static(
        type: EffectType,
        target: str,
        value: float,
        condition: Requirement | None = None,
    ) -> EffectDef:
        """Constant value effect."""
        return EffectDef(type=type, target=target, value=value, condition=condition)

    @staticmethod
    def synergy(
        source: str,
        type: EffectType,
        target: str,
        per_unit: float,
        condition: Requirement | None = None,
    ) -> EffectDef:
        """Value scales with count of a *different* element (source)."""
        _source = source
        _per_unit = per_unit

        def _value(state: GameState) -> float:
            return state.element_count(_source) * _per_unit

        return EffectDef(type=type, target=target, value=_value, condition=condition)
