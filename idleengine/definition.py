from __future__ import annotations

import warnings
from dataclasses import dataclass, field

from idleengine.currency import CurrencyDef
from idleengine.element import ElementDef
from idleengine.milestone import MilestoneDef
from idleengine.prestige import PrestigeLayerDef


@dataclass
class GameConfig:
    """Top-level game configuration."""

    name: str = "Untitled"
    tick_rate: int = 10


@dataclass
class ClickTarget:
    """Defines a clickable currency source."""

    currency: str = ""
    base_value: float = 1.0


@dataclass
class GameDefinition:
    """Complete static definition of an idle game."""

    config: GameConfig = field(default_factory=GameConfig)
    currencies: list[CurrencyDef] = field(default_factory=list)
    elements: list[ElementDef] = field(default_factory=list)
    milestones: list[MilestoneDef] = field(default_factory=list)
    prestige_layers: list[PrestigeLayerDef] = field(default_factory=list)
    pacing_bounds: list = field(default_factory=list)  # list[PacingBound]
    click_targets: list[ClickTarget] = field(default_factory=list)

    # Lookup dicts built in __post_init__
    _currencies_by_id: dict[str, CurrencyDef] = field(
        default_factory=dict, init=False, repr=False
    )
    _elements_by_id: dict[str, ElementDef] = field(
        default_factory=dict, init=False, repr=False
    )
    _milestones_by_id: dict[str, MilestoneDef] = field(
        default_factory=dict, init=False, repr=False
    )
    _prestige_by_id: dict[str, PrestigeLayerDef] = field(
        default_factory=dict, init=False, repr=False
    )
    _click_targets_by_currency: dict[str, ClickTarget] = field(
        default_factory=dict, init=False, repr=False
    )

    def __post_init__(self) -> None:
        self._currencies_by_id = {c.id: c for c in self.currencies}
        self._elements_by_id = {e.id: e for e in self.elements}
        self._milestones_by_id = {m.id: m for m in self.milestones}
        self._prestige_by_id = {p.id: p for p in self.prestige_layers}
        self._click_targets_by_currency = {ct.currency: ct for ct in self.click_targets}

    def get_currency(self, id: str) -> CurrencyDef | None:
        return self._currencies_by_id.get(id)

    def get_element(self, id: str) -> ElementDef | None:
        return self._elements_by_id.get(id)

    def get_milestone(self, id: str) -> MilestoneDef | None:
        return self._milestones_by_id.get(id)

    def get_prestige_layer(self, id: str) -> PrestigeLayerDef | None:
        return self._prestige_by_id.get(id)

    def get_click_target(self, currency: str) -> ClickTarget | None:
        return self._click_targets_by_currency.get(currency)

    def validate(self) -> list[str]:
        """Check for common definition errors. Returns list of error messages."""
        errors: list[str] = []
        currency_ids = {c.id for c in self.currencies}
        element_ids = {e.id for e in self.elements}

        # Check for duplicate IDs
        seen_c: set[str] = set()
        for c in self.currencies:
            if c.id in seen_c:
                errors.append(f"Duplicate currency ID: {c.id!r}")
            seen_c.add(c.id)

        seen_e: set[str] = set()
        for e in self.elements:
            if e.id in seen_e:
                errors.append(f"Duplicate element ID: {e.id!r}")
            seen_e.add(e.id)

        seen_m: set[str] = set()
        for m in self.milestones:
            if m.id in seen_m:
                errors.append(f"Duplicate milestone ID: {m.id!r}")
            seen_m.add(m.id)

        # Check element cost currencies exist
        for e in self.elements:
            for cur_id in e.base_cost:
                if cur_id not in currency_ids:
                    errors.append(
                        f"Element {e.id!r} references unknown currency {cur_id!r} in base_cost"
                    )

        # Check effect targets reference known currencies
        for e in self.elements:
            for eff in e.effects:
                from idleengine.effect import EffectType
                if eff.type in (
                    EffectType.PRODUCTION_FLAT,
                    EffectType.PRODUCTION_ADD_PCT,
                    EffectType.PRODUCTION_MULT,
                    EffectType.CLICK_FLAT,
                    EffectType.CLICK_MULT,
                    EffectType.CAP_FLAT,
                    EffectType.CAP_MULT,
                    EffectType.AUTO_CLICK,
                    EffectType.GRANT,
                ):
                    if eff.target not in currency_ids:
                        errors.append(
                            f"Element {e.id!r} has effect targeting unknown currency {eff.target!r}"
                        )
                elif eff.type in (EffectType.COST_MULT, EffectType.UNLOCK):
                    if eff.target not in element_ids:
                        errors.append(
                            f"Element {e.id!r} has effect targeting unknown element {eff.target!r}"
                        )

        # Check click targets reference known currencies
        for ct in self.click_targets:
            if ct.currency not in currency_ids:
                errors.append(f"ClickTarget references unknown currency {ct.currency!r}")

        # Check prestige layers
        for p in self.prestige_layers:
            if p.prestige_currency not in currency_ids:
                errors.append(
                    f"PrestigeLayer {p.id!r} references unknown currency {p.prestige_currency!r}"
                )
            if isinstance(p.currencies_reset, list):
                for cid in p.currencies_reset:
                    if cid not in currency_ids:
                        errors.append(
                            f"PrestigeLayer {p.id!r} resets unknown currency {cid!r}"
                        )
            if isinstance(p.elements_reset, list):
                for eid in p.elements_reset:
                    if eid not in element_ids:
                        errors.append(
                            f"PrestigeLayer {p.id!r} resets unknown element {eid!r}"
                        )

        # Warn about per_count() used with multiplicative effect types
        from idleengine.effect import EffectType

        for e in self.elements:
            for eff in e.effects:
                if (
                    getattr(eff, "_created_by", None) == "per_count"
                    and eff.type
                    in (EffectType.PRODUCTION_MULT, EffectType.GLOBAL_MULT)
                ):
                    per_unit = getattr(eff, "_per_unit_value", None)
                    val_at_2 = f"{2 * per_unit}" if per_unit is not None else "?"
                    warnings.warn(
                        f"Element {e.id!r} uses per_count() with {eff.type.name} on "
                        f"{eff.target!r}. This gives linear multiplication "
                        f"(count * per_unit), not exponential (per_unit^count). "
                        f"At count=2, the multiplier will be 2*per_unit = {val_at_2}, "
                        f"which likely doubles production. "
                        f"Consider using Effect.per_count_exponential() for "
                        f"compounding multipliers.",
                        stacklevel=2,
                    )

        return errors
