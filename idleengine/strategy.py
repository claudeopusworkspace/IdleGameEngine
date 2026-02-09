from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from idleengine.element import ElementStatus
from idleengine.requirement import Requirement

if TYPE_CHECKING:
    from idleengine.state import GameState
    from idleengine.runtime import GameRuntime


@dataclass
class ClickProfile:
    """Configures click behavior for strategies."""

    targets: dict[str, float] = field(default_factory=dict)  # currency -> CPS
    active_until: Requirement | None = None
    active_during_wait: bool = False

    def get_clicks(
        self, state: GameState, duration: float, is_waiting: bool = False
    ) -> dict[str, int]:
        """Return number of clicks per target for the given duration."""
        if self.active_until is not None and self.active_until.evaluate(state):
            return {}
        if is_waiting and not self.active_during_wait:
            return {}

        result: dict[str, int] = {}
        for currency, cps in self.targets.items():
            clicks = int(cps * duration)
            if clicks > 0:
                result[currency] = clicks
        return result


class Strategy(ABC):
    """Base class for simulation strategies."""

    @abstractmethod
    def decide_purchases(
        self, state: GameState, affordable: list[ElementStatus]
    ) -> list[str]:
        """Return ordered list of element IDs to buy."""
        ...

    def get_clicks(
        self, state: GameState, duration: float, is_waiting: bool = False
    ) -> dict[str, int]:
        """Return clicks per target during this tick. Override or use click_profile."""
        return {}

    def should_prestige(self, state: GameState, layer_id: str) -> bool:
        """Whether to trigger this prestige layer now."""
        return False

    @abstractmethod
    def describe(self) -> str: ...


class GreedyCheapest(Strategy):
    """Buy the cheapest affordable element first."""

    def __init__(
        self,
        click_profile: ClickProfile | None = None,
        prestige_mode: str = "never",
        cost_weights: dict[str, float] | None = None,
    ) -> None:
        self.click_profile = click_profile
        self.prestige_mode = prestige_mode  # "never" or "first_opportunity"
        self.cost_weights = cost_weights or {}

    def _weighted_cost(self, cost: dict[str, float]) -> float:
        total = 0.0
        for cur, amt in cost.items():
            weight = self.cost_weights.get(cur, 1.0)
            total += amt * weight
        return total

    def decide_purchases(
        self, state: GameState, affordable: list[ElementStatus]
    ) -> list[str]:
        if not affordable:
            return []
        sorted_elements = sorted(
            affordable, key=lambda e: self._weighted_cost(e.current_cost)
        )
        return [e.id for e in sorted_elements]

    def get_clicks(
        self, state: GameState, duration: float, is_waiting: bool = False
    ) -> dict[str, int]:
        if self.click_profile:
            return self.click_profile.get_clicks(state, duration, is_waiting)
        return {}

    def should_prestige(self, state: GameState, layer_id: str) -> bool:
        return self.prestige_mode == "first_opportunity"

    def describe(self) -> str:
        parts = ["GreedyCheapest"]
        if self.click_profile and self.click_profile.targets:
            cps_str = ", ".join(
                f"{k}:{v}" for k, v in self.click_profile.targets.items()
            )
            parts.append(f"({cps_str} CPS)")
        return " ".join(parts)


class GreedyROI(Strategy):
    """Buy the element with the best immediate rate-of-return."""

    def __init__(
        self,
        runtime: GameRuntime | None = None,
        click_profile: ClickProfile | None = None,
        prestige_mode: str = "never",
    ) -> None:
        self.runtime = runtime
        self.click_profile = click_profile
        self.prestige_mode = prestige_mode

    def decide_purchases(
        self, state: GameState, affordable: list[ElementStatus]
    ) -> list[str]:
        if not affordable or self.runtime is None:
            return [e.id for e in affordable] if affordable else []

        # Compute current total rate
        current_total_rate = sum(
            state.currency_rate(cdef.id)
            for cdef in self.runtime.definition.currencies
        )

        scored: list[tuple[str, float]] = []
        for elem in affordable:
            cost_total = sum(elem.current_cost.values())
            if cost_total <= 0:
                scored.append((elem.id, float("inf")))
                continue

            # Simulate purchase: save state, buy, measure rate change
            old_rates = {
                cdef.id: state.currency_rate(cdef.id)
                for cdef in self.runtime.definition.currencies
            }
            if self.runtime.try_purchase(elem.id):
                self.runtime._dirty = True
                self.runtime._recompute_rates()
                new_total = sum(
                    state.currency_rate(cdef.id)
                    for cdef in self.runtime.definition.currencies
                )
                delta_rate = new_total - current_total_rate
                roi = delta_rate / cost_total if cost_total > 0 else 0
                scored.append((elem.id, roi))

                # Undo: restore currencies, decrement count
                es = state.elements[elem.id]
                es.count -= 1
                edef = self.runtime.definition.get_element(elem.id)
                if edef:
                    cost = edef.cost_scaling.compute(edef.base_cost, es.count)
                    cost = self.runtime._apply_cost_effects(elem.id, cost)
                    for cid, amt in cost.items():
                        state.currencies[cid].current += amt
                # Restore rates
                for cid, rate in old_rates.items():
                    state.currencies[cid].current_rate = rate
                self.runtime._dirty = True

        scored.sort(key=lambda x: -x[1])
        return [eid for eid, _ in scored]

    def get_clicks(
        self, state: GameState, duration: float, is_waiting: bool = False
    ) -> dict[str, int]:
        if self.click_profile:
            return self.click_profile.get_clicks(state, duration, is_waiting)
        return {}

    def should_prestige(self, state: GameState, layer_id: str) -> bool:
        return self.prestige_mode == "first_opportunity"

    def describe(self) -> str:
        return "GreedyROI"


class SaveForBest(Strategy):
    """Save for the single highest-ROI available element."""

    def __init__(
        self,
        runtime: GameRuntime | None = None,
        click_profile: ClickProfile | None = None,
    ) -> None:
        self.runtime = runtime
        self.click_profile = click_profile
        self._saving_for: str | None = None

    def decide_purchases(
        self, state: GameState, affordable: list[ElementStatus]
    ) -> list[str]:
        # If we're saving for something and it's affordable, buy it
        if self._saving_for:
            for elem in affordable:
                if elem.id == self._saving_for:
                    self._saving_for = None
                    return [elem.id]
            # Still saving — don't buy anything else
            return []

        # Pick the best available (not just affordable) to save for
        if self.runtime:
            available = self.runtime.get_available_purchases()
            if available:
                # Simple heuristic: pick cheapest available that we can't afford yet
                not_affordable = [e for e in available if not e.affordable]
                if not_affordable:
                    cheapest = min(
                        not_affordable, key=lambda e: sum(e.current_cost.values())
                    )
                    self._saving_for = cheapest.id
                    return []

        # Fallback: buy cheapest affordable
        if affordable:
            cheapest = min(affordable, key=lambda e: sum(e.current_cost.values()))
            return [cheapest.id]
        return []

    def get_clicks(
        self, state: GameState, duration: float, is_waiting: bool = False
    ) -> dict[str, int]:
        if self.click_profile:
            return self.click_profile.get_clicks(state, duration, is_waiting)
        return {}

    def describe(self) -> str:
        return "SaveForBest"


class PriorityList(Strategy):
    """Follow a designer-specified purchase order."""

    def __init__(
        self,
        priorities: list[tuple[str, int]],
        fallback: Strategy | None = None,
        click_profile: ClickProfile | None = None,
    ) -> None:
        self.priorities = priorities  # (element_id, target_count)
        self.fallback = fallback
        self.click_profile = click_profile

    def decide_purchases(
        self, state: GameState, affordable: list[ElementStatus]
    ) -> list[str]:
        affordable_ids = {e.id for e in affordable}

        for element_id, target_count in self.priorities:
            if element_id in affordable_ids:
                current = state.element_count(element_id)
                if current < target_count:
                    return [element_id]

        # All priorities met or not affordable — use fallback
        if self.fallback:
            return self.fallback.decide_purchases(state, affordable)
        return []

    def get_clicks(
        self, state: GameState, duration: float, is_waiting: bool = False
    ) -> dict[str, int]:
        if self.click_profile:
            return self.click_profile.get_clicks(state, duration, is_waiting)
        return {}

    def describe(self) -> str:
        items = ", ".join(f"{eid}x{cnt}" for eid, cnt in self.priorities)
        return f"PriorityList([{items}])"


class CustomStrategy(Strategy):
    """Strategy defined by callables."""

    def __init__(
        self,
        decide_fn: Callable[
            [GameState, list[ElementStatus]], list[str]
        ] | None = None,
        clicks_fn: Callable[
            [GameState, float, bool], dict[str, int]
        ] | None = None,
        prestige_fn: Callable[[GameState, str], bool] | None = None,
        name: str = "Custom",
    ) -> None:
        self._decide_fn = decide_fn
        self._clicks_fn = clicks_fn
        self._prestige_fn = prestige_fn
        self._name = name

    def decide_purchases(
        self, state: GameState, affordable: list[ElementStatus]
    ) -> list[str]:
        if self._decide_fn:
            return self._decide_fn(state, affordable)
        return []

    def get_clicks(
        self, state: GameState, duration: float, is_waiting: bool = False
    ) -> dict[str, int]:
        if self._clicks_fn:
            return self._clicks_fn(state, duration, is_waiting)
        return {}

    def should_prestige(self, state: GameState, layer_id: str) -> bool:
        if self._prestige_fn:
            return self._prestige_fn(state, layer_id)
        return False

    def describe(self) -> str:
        return self._name


STRATEGY_REGISTRY: dict[str, type[Strategy]] = {
    "greedy_cheapest": GreedyCheapest,
    "greedy_roi": GreedyROI,
    "save_for_best": SaveForBest,
    "priority_list": PriorityList,
    "custom": CustomStrategy,
}
