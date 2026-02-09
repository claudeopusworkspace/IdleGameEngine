from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

from idleengine._types import resolve_optional
from idleengine.definition import GameDefinition
from idleengine.effect import EffectDef, EffectPhase, EffectType
from idleengine.element import ElementStatus
from idleengine.pipeline import ProductionPipeline
from idleengine.prestige import PrestigeResult
from idleengine.state import GameState

if TYPE_CHECKING:
    from idleengine.subsystem import Subsystem


class GameRuntime:
    """Authoritative game logic processor."""

    def __init__(self, definition: GameDefinition) -> None:
        errors = definition.validate()
        if errors:
            raise ValueError(
                "Invalid GameDefinition:\n" + "\n".join(f"  - {e}" for e in errors)
            )

        self.definition = definition
        self.state = GameState(definition)
        self.pipeline = ProductionPipeline()
        self._dirty = True
        self._subsystems: list[Subsystem] = []
        self._custom_effect_handlers: dict[str, Callable] = {}

        # Initialize element availability so purchases work before first tick
        self._update_element_statuses()

    # ── Core loop ────────────────────────────────────────────────────

    def tick(self, delta: float) -> None:
        """Advance the game by *delta* seconds."""
        if self._dirty:
            self._recompute_rates()
            self._dirty = False

        # Apply production
        for cdef in self.definition.currencies:
            cs = self.state.currencies[cdef.id]
            if cs.current_rate != 0.0:
                earned = cs.current_rate * delta
                cs.current += earned
                if earned > 0:
                    cs.total_earned += earned
                cap = self._resolve_cap(cdef.id)
                if cap is not None and cs.current > cap:
                    cs.current = cap

        # Process auto-clicks
        self._process_auto_clicks(delta)

        # Advance time
        self.state.time_elapsed += delta

        # Update element statuses
        self._update_element_statuses()

        # Check milestones
        self._check_milestones()

        # Tick subsystems
        for sub in self._subsystems:
            sub.tick(self.state, delta)

    # ── Player actions ───────────────────────────────────────────────

    def try_purchase(self, element_id: str) -> bool:
        """Attempt to purchase an element. Returns True on success."""
        edef = self.definition.get_element(element_id)
        if edef is None:
            return False

        es = self.state.elements[element_id]

        # Check max count
        if edef.max_count is not None and es.count >= edef.max_count:
            return False

        # Check availability (requirements met or unlocked)
        if not es.available and not es.unlocked:
            return False

        # Check purchase requirements
        for req in edef.purchase_requirements:
            if not req.evaluate(self.state):
                return False

        # Compute current cost
        cost = edef.cost_scaling.compute(edef.base_cost, es.count)

        # Apply COST_MULT effects
        cost = self._apply_cost_effects(element_id, cost)

        # Check affordability
        for cur_id, amount in cost.items():
            if self.state.currency_value(cur_id) < amount:
                return False

        # Deduct costs
        for cur_id, amount in cost.items():
            self.state.currencies[cur_id].current -= amount

        # Increment count
        es.count += 1

        # Apply IMMEDIATE effects
        for eff in edef.effects:
            if eff.phase == EffectPhase.IMMEDIATE:
                self._apply_immediate_effect(eff)

        # Fire on_purchase callback
        if edef.on_purchase is not None:
            edef.on_purchase(self.state)

        # Mark dirty
        self._dirty = True
        self._update_element_statuses()
        return True

    def process_click(self, target_currency: str) -> float:
        """Process a click on a target currency. Returns the amount added."""
        ct = self.definition.get_click_target(target_currency)
        if ct is None:
            return 0.0

        # Collect click effects
        click_effects: list[tuple[EffectType, float]] = []
        for edef in self.definition.elements:
            es = self.state.elements[edef.id]
            if es.count <= 0:
                continue
            for eff in edef.effects:
                if eff.type in (EffectType.CLICK_FLAT, EffectType.CLICK_MULT):
                    if eff.target == target_currency and eff.is_active(self.state):
                        click_effects.append((eff.type, eff.resolve(self.state)))

        value = self.pipeline.compute_click_value(
            target_currency, ct.base_value, click_effects, self.state
        )
        cs = self.state.currencies[target_currency]
        cs.current += value
        cs.total_earned += value

        cap = self._resolve_cap(target_currency)
        if cap is not None and cs.current > cap:
            cs.current = cap

        return value

    def trigger_prestige(self, layer_id: str) -> PrestigeResult:
        """Trigger a prestige reset. Returns a PrestigeResult."""
        layer = self.definition.get_prestige_layer(layer_id)
        if layer is None:
            return PrestigeResult(success=False, reason="Unknown prestige layer")

        # Check requirements
        for req in layer.requirements:
            if not req.evaluate(self.state):
                return PrestigeResult(success=False, reason="Requirements not met")

        # Compute reward
        if layer.reward_formula is None:
            return PrestigeResult(success=False, reason="No reward formula")

        reward = layer.reward_formula(self.state)
        if reward < layer.minimum_reward:
            return PrestigeResult(
                success=False,
                reward_amount=reward,
                reason=f"Reward {reward:.2f} below minimum {layer.minimum_reward:.2f}",
            )

        # Resolve reset lists
        currencies_to_reset = self._resolve_reset_list(
            layer.currencies_reset, "currency"
        )
        elements_to_reset = self._resolve_reset_list(layer.elements_reset, "element")

        # Reset currencies
        for cid in currencies_to_reset:
            cs = self.state.currencies.get(cid)
            if cs:
                cdef = self.definition.get_currency(cid)
                cs.current = cdef.initial_value if cdef else 0.0
                cs.total_earned = cdef.initial_value if cdef else 0.0
                cs.current_rate = 0.0

        # Reset elements
        for eid in elements_to_reset:
            es = self.state.elements.get(eid)
            if es:
                edef = self.definition.get_element(eid)
                if edef and "persistent" not in edef.tags:
                    es.count = 0
                    es.available = False
                    es.affordable = False

        # Grant prestige currency
        pcs = self.state.currencies.get(layer.prestige_currency)
        if pcs:
            pcs.current += reward
            pcs.total_earned += reward

        # Increment counters
        self.state.prestige_counts[layer_id] = (
            self.state.prestige_counts.get(layer_id, 0) + 1
        )
        self.state.run_number += 1

        self._dirty = True
        self._update_element_statuses()

        return PrestigeResult(
            success=True,
            reward_amount=reward,
            currencies_reset=currencies_to_reset,
            elements_reset=elements_to_reset,
        )

    # ── Queries ──────────────────────────────────────────────────────

    def get_state(self) -> GameState:
        """Return live reference to game state."""
        return self.state

    def get_available_purchases(self) -> list[ElementStatus]:
        """Return elements that are available (requirements met)."""
        result: list[ElementStatus] = []
        for edef in self.definition.elements:
            es = self.state.elements[edef.id]
            if not (es.available or es.unlocked):
                continue
            if edef.max_count is not None and es.count >= edef.max_count:
                continue
            cost = edef.cost_scaling.compute(edef.base_cost, es.count)
            cost = self._apply_cost_effects(edef.id, cost)
            result.append(
                ElementStatus(
                    id=edef.id,
                    display_name=edef.display_name,
                    count=es.count,
                    available=True,
                    affordable=es.affordable,
                    current_cost=cost,
                    max_count=edef.max_count,
                    category=edef.category,
                    tags=frozenset(edef.tags),
                )
            )
        return result

    def get_affordable_purchases(self) -> list[ElementStatus]:
        """Return elements that are both available and affordable."""
        return [e for e in self.get_available_purchases() if e.affordable]

    def compute_current_cost(self, element_id: str) -> dict[str, float]:
        edef = self.definition.get_element(element_id)
        if edef is None:
            return {}
        es = self.state.elements[element_id]
        cost = edef.cost_scaling.compute(edef.base_cost, es.count)
        return self._apply_cost_effects(element_id, cost)

    def compute_time_to_afford(self, element_id: str) -> float | None:
        """Seconds until affordable at current rates. None if impossible."""
        cost = self.compute_current_cost(element_id)
        if not cost:
            return None

        max_time = 0.0
        for cur_id, amount in cost.items():
            current = self.state.currency_value(cur_id)
            if current >= amount:
                continue
            rate = self.state.currency_rate(cur_id)
            if rate <= 0:
                return None  # will never afford
            needed = amount - current
            t = needed / rate
            if t > max_time:
                max_time = t
        return max_time

    # ── Extension points ─────────────────────────────────────────────

    def register_effect_type(self, name: str, handler: Callable) -> None:
        self._custom_effect_handlers[name] = handler

    def set_production_pipeline(self, currency_id: str, fn: Callable) -> None:
        self.pipeline.set_custom(currency_id, fn)

    def add_subsystem(self, subsystem: Subsystem) -> None:
        self._subsystems.append(subsystem)

    # ── Private helpers ──────────────────────────────────────────────

    def _recompute_rates(self) -> None:
        """Collect all active effects and compute production rates."""
        # Gather global effects
        global_effects: list[tuple[EffectType, float]] = []
        per_currency: dict[str, list[tuple[EffectType, float]]] = {
            cdef.id: [] for cdef in self.definition.currencies
        }

        for edef in self.definition.elements:
            es = self.state.elements[edef.id]
            if es.count <= 0:
                continue
            for eff in edef.effects:
                if eff.phase in (EffectPhase.IMMEDIATE, EffectPhase.COST):
                    continue
                if not eff.is_active(self.state):
                    continue
                resolved = eff.resolve(self.state)
                pair = (eff.type, resolved)
                if eff.type is EffectType.GLOBAL_MULT:
                    global_effects.append(pair)
                elif eff.target in per_currency:
                    per_currency[eff.target].append(pair)

        for cdef in self.definition.currencies:
            effects = per_currency[cdef.id] + global_effects
            rate = self.pipeline.compute_rate(cdef.id, effects, self.state)
            self.state.currencies[cdef.id].current_rate = rate

    def _update_element_statuses(self) -> None:
        """Update availability and affordability for all elements."""
        for edef in self.definition.elements:
            es = self.state.elements[edef.id]

            # Available if all requirements met (or unlocked)
            if not es.unlocked:
                es.available = all(
                    r.evaluate(self.state) for r in edef.requirements
                ) if edef.requirements else True
            else:
                es.available = True

            # Affordable if we can pay the cost
            if es.available and (
                edef.max_count is None or es.count < edef.max_count
            ):
                cost = edef.cost_scaling.compute(edef.base_cost, es.count)
                cost = self._apply_cost_effects(edef.id, cost)
                es.affordable = all(
                    self.state.currency_value(cid) >= amt
                    for cid, amt in cost.items()
                )
            else:
                es.affordable = False

    def _check_milestones(self) -> None:
        """Fire milestones whose triggers are now met."""
        for mdef in self.definition.milestones:
            if mdef.id in self.state.milestones_reached:
                continue
            if mdef.trigger is not None and mdef.trigger.evaluate(self.state):
                self.state.milestones_reached[mdef.id] = self.state.time_elapsed
                if mdef.on_trigger is not None:
                    mdef.on_trigger(self.state)

    def _apply_immediate_effect(self, eff: EffectDef) -> None:
        """Apply a one-time immediate effect (GRANT or UNLOCK)."""
        if eff.type is EffectType.GRANT:
            cs = self.state.currencies.get(eff.target)
            if cs:
                amount = eff.resolve(self.state)
                cs.current += amount
                if amount > 0:
                    cs.total_earned += amount
        elif eff.type is EffectType.UNLOCK:
            es = self.state.elements.get(eff.target)
            if es:
                es.unlocked = True
                es.available = True

    def _process_auto_clicks(self, delta: float) -> None:
        """Process AUTO_CLICK effects."""
        for edef in self.definition.elements:
            es = self.state.elements[edef.id]
            if es.count <= 0:
                continue
            for eff in edef.effects:
                if eff.type is not EffectType.AUTO_CLICK:
                    continue
                if not eff.is_active(self.state):
                    continue
                clicks_per_sec = eff.resolve(self.state)
                total_clicks = clicks_per_sec * delta
                # Apply each auto-click through the click pipeline
                ct = self.definition.get_click_target(eff.target)
                if ct:
                    value = ct.base_value * total_clicks
                    cs = self.state.currencies.get(eff.target)
                    if cs:
                        cs.current += value
                        cs.total_earned += value

    def _resolve_cap(self, currency_id: str) -> float | None:
        """Resolve the effective cap for a currency, including CAP effects."""
        cdef = self.definition.get_currency(currency_id)
        if cdef is None:
            return None

        base_cap = resolve_optional(cdef.cap, self.state)
        if base_cap is None:
            return None

        cap_flat = 0.0
        cap_mult = 1.0
        for edef in self.definition.elements:
            es = self.state.elements[edef.id]
            if es.count <= 0:
                continue
            for eff in edef.effects:
                if eff.target != currency_id:
                    continue
                if not eff.is_active(self.state):
                    continue
                if eff.type is EffectType.CAP_FLAT:
                    cap_flat += eff.resolve(self.state)
                elif eff.type is EffectType.CAP_MULT:
                    cap_mult *= eff.resolve(self.state)

        return (base_cap + cap_flat) * cap_mult

    def _apply_cost_effects(
        self, element_id: str, cost: dict[str, float]
    ) -> dict[str, float]:
        """Apply COST_MULT effects targeting this element."""
        total_mult = 1.0
        for edef in self.definition.elements:
            es = self.state.elements[edef.id]
            if es.count <= 0:
                continue
            for eff in edef.effects:
                if eff.type is EffectType.COST_MULT and eff.target == element_id:
                    if eff.is_active(self.state):
                        total_mult *= eff.resolve(self.state)

        if total_mult != 1.0:
            return {k: v * total_mult for k, v in cost.items()}
        return cost

    def _resolve_reset_list(
        self, spec: list[str] | str, kind: str
    ) -> list[str]:
        """Resolve 'all_non_persistent' or explicit list."""
        if spec == "all_non_persistent":
            if kind == "currency":
                return [
                    c.id
                    for c in self.definition.currencies
                    if not c.persistent
                ]
            else:
                return [
                    e.id
                    for e in self.definition.elements
                    if "persistent" not in e.tags
                ]
        if isinstance(spec, list):
            return list(spec)
        return []
