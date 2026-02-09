from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from idleengine.effect import EffectType

if TYPE_CHECKING:
    from idleengine.state import GameState


class ProductionPipeline:
    """Computes production rates using the 4-phase pipeline."""

    def __init__(self) -> None:
        self._custom: dict[str, Callable[..., float]] = {}

    def set_custom(self, currency_id: str, fn: Callable[..., float]) -> None:
        """Register a custom pipeline for a specific currency."""
        self._custom[currency_id] = fn

    def compute_rate(
        self,
        currency_id: str,
        effects: list[tuple[EffectType, float]],
        state: GameState,
    ) -> float:
        """Compute production rate for a currency from pre-resolved effects.

        effects is a list of (EffectType, resolved_value) tuples.
        """
        if currency_id in self._custom:
            return self._custom[currency_id](currency_id, effects, state)

        flat_sum = 0.0
        add_pct = 0.0
        mult = 1.0
        global_mult = 1.0

        for etype, val in effects:
            if etype is EffectType.PRODUCTION_FLAT:
                flat_sum += val
            elif etype is EffectType.PRODUCTION_ADD_PCT:
                add_pct += val
            elif etype is EffectType.PRODUCTION_MULT:
                mult *= val
            elif etype is EffectType.GLOBAL_MULT:
                global_mult *= val

        return flat_sum * (1.0 + add_pct) * mult * global_mult

    def compute_click_value(
        self,
        currency_id: str,
        base_value: float,
        effects: list[tuple[EffectType, float]],
        state: GameState,
    ) -> float:
        """Compute click value for a currency from pre-resolved effects."""
        flat_sum = base_value
        click_mult = 1.0

        for etype, val in effects:
            if etype is EffectType.CLICK_FLAT:
                flat_sum += val
            elif etype is EffectType.CLICK_MULT:
                click_mult *= val

        return flat_sum * click_mult
