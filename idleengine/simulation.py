from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from idleengine.definition import GameDefinition
from idleengine.state import GameState
from idleengine.metrics import MetricsCollector
from idleengine.report import SimulationReport, build_report
from idleengine.requirement import EstimatedTimeRequirement
from idleengine.runtime import GameRuntime
from idleengine.strategy import Strategy
from idleengine.terminal import SimulationContext, TerminalCondition

MAX_TICKS = 10_000_000


class Simulation:
    """Orchestrates a headless simulation of a game definition."""

    def __init__(
        self,
        definition: GameDefinition,
        strategy: Strategy,
        terminal: TerminalCondition,
        tick_resolution: float = 1.0,
        seed: int | None = None,
        mode: str = "tick",
    ) -> None:
        self.definition = definition
        self.strategy = strategy
        self.terminal = terminal
        self.tick_resolution = tick_resolution
        self.mode = mode

        self.rng = random.Random(seed)
        self.runtime = GameRuntime(definition)
        self.collector = MetricsCollector(snapshot_interval=tick_resolution)
        self.context = SimulationContext()

        # Inject RNG into EstimatedTimeRequirements
        self._inject_rng(definition)

    def _inject_rng(self, definition: GameDefinition) -> None:
        """Find all EstimatedTimeRequirements and inject the RNG."""
        for edef in definition.elements:
            for req in edef.requirements:
                self._inject_into_req(req)
            for req in edef.purchase_requirements:
                self._inject_into_req(req)
        for mdef in definition.milestones:
            if mdef.trigger is not None:
                self._inject_into_req(mdef.trigger)
        for pdef in definition.prestige_layers:
            for req in pdef.requirements:
                self._inject_into_req(req)

    def _inject_into_req(self, req: object) -> None:
        if isinstance(req, EstimatedTimeRequirement):
            req.inject_rng(self.rng)
        # Recurse into composite requirements
        if hasattr(req, "reqs"):
            for sub in req.reqs:
                self._inject_into_req(sub)

    def run(self) -> SimulationReport:
        if self.mode == "event_jump":
            return self._run_event_jump()
        return self._run_tick()

    def _run_tick(self) -> SimulationReport:
        state = self.runtime.get_state()
        milestones_seen: set[str] = set()
        tick_count = 0

        while not self.terminal.is_met(state, self.context):
            tick_count += 1
            if tick_count > MAX_TICKS:
                break

            # 1. Advance time
            self.runtime.tick(self.tick_resolution)

            # 2. Process clicks
            clicks = self.strategy.get_clicks(state, self.tick_resolution)
            for target, count in clicks.items():
                for _ in range(count):
                    self.runtime.process_click(target)

            # 3. Evaluate purchases
            affordable = self.runtime.get_affordable_purchases()
            to_buy = self.strategy.decide_purchases(state, affordable)
            for element_id in to_buy:
                cost = self.runtime.compute_current_cost(element_id)
                if self.runtime.try_purchase(element_id):
                    self.collector.record_purchase(state, element_id, cost)
                    self.context.last_purchase_time = state.time_elapsed
                    self.context.total_purchases += 1
                    # Re-get affordable since state changed
                    affordable = self.runtime.get_affordable_purchases()

            # 4. Evaluate prestige
            for layer in self.definition.prestige_layers:
                if self.strategy.should_prestige(state, layer.id):
                    result = self.runtime.trigger_prestige(layer.id)
                    if result.success:
                        self.collector.record_prestige(
                            state, layer.id, result.reward_amount, state.time_elapsed
                        )

            # 5. Check for new milestones
            for mid, mtime in state.milestones_reached.items():
                if mid not in milestones_seen:
                    milestones_seen.add(mid)
                    self.collector.record_milestone(state, mid)

            # 6. Record metrics
            self.collector.record_tick(state)

            # Safety: NaN/Inf detection
            for cs in state.currencies.values():
                if math.isnan(cs.current) or math.isinf(cs.current):
                    return self._build_report("Aborted: NaN/Inf detected")

        outcome = "Terminal condition met" if self.terminal.is_met(state, self.context) else "Max ticks reached"
        return self._build_report(outcome)

    def _compute_click_income_rate(self, state: GameState) -> dict[str, float]:
        """Estimate income per second from clicks (for event-jump planning)."""
        clicks_per_sec = self.strategy.get_clicks(state, 1.0, is_waiting=True)
        income: dict[str, float] = {}
        for target, count in clicks_per_sec.items():
            ct = self.definition.get_click_target(target)
            if ct and count > 0:
                income[target] = ct.base_value * count
        return income

    def _compute_time_to_afford_with_clicks(
        self, element_id: str, click_income: dict[str, float]
    ) -> float | None:
        """Time to afford considering both production rate and click income."""
        cost = self.runtime.compute_current_cost(element_id)
        if not cost:
            return None

        state = self.runtime.get_state()
        max_time = 0.0
        for cur_id, amount in cost.items():
            current = state.currency_value(cur_id)
            if current >= amount:
                continue
            rate = state.currency_rate(cur_id) + click_income.get(cur_id, 0.0)
            if rate <= 0:
                return None
            needed = amount - current
            t = needed / rate
            if t > max_time:
                max_time = t
        return max_time

    def _run_event_jump(self) -> SimulationReport:
        state = self.runtime.get_state()
        milestones_seen: set[str] = set()
        iterations = 0

        # Initial tick to set up state
        self.runtime.tick(0)
        self.runtime._update_element_statuses()

        while not self.terminal.is_met(state, self.context):
            iterations += 1
            if iterations > MAX_TICKS:
                break

            affordable = self.runtime.get_affordable_purchases()

            if affordable:
                to_buy = self.strategy.decide_purchases(state, affordable)
                for element_id in to_buy:
                    cost = self.runtime.compute_current_cost(element_id)
                    if self.runtime.try_purchase(element_id):
                        self.collector.record_purchase(state, element_id, cost)
                        self.context.last_purchase_time = state.time_elapsed
                        self.context.total_purchases += 1
                        affordable = self.runtime.get_affordable_purchases()
            else:
                # Find next affordable element, including click income
                available = self.runtime.get_available_purchases()
                click_income = self._compute_click_income_rate(state)

                times: dict[str, float] = {}
                for elem in available:
                    # Try with production only first
                    t = self.runtime.compute_time_to_afford(elem.id)
                    if t is None and click_income:
                        # Try again with click income
                        t = self._compute_time_to_afford_with_clicks(
                            elem.id, click_income
                        )
                    if t is not None and t >= 0:
                        times[elem.id] = t

                if not times:
                    self.collector.record_stall(state)
                    self.context.stall_detected = True
                    break

                next_id = min(times, key=lambda k: times[k])
                jump_duration = times[next_id]

                if jump_duration <= 0:
                    jump_duration = self.tick_resolution

                # Apply clicks during wait
                clicks = self.strategy.get_clicks(state, jump_duration, is_waiting=True)
                for target, count in clicks.items():
                    ct = self.definition.get_click_target(target)
                    if ct:
                        cs = state.currencies.get(target)
                        if cs:
                            earned = ct.base_value * count
                            cs.current += earned
                            cs.total_earned += earned

                self.runtime.tick(jump_duration)
                self.collector.record_wait(state, jump_duration)

            # Check for new milestones
            for mid, mtime in state.milestones_reached.items():
                if mid not in milestones_seen:
                    milestones_seen.add(mid)
                    self.collector.record_milestone(state, mid)

            self.collector.record_tick(state)

            # Safety
            for cs in state.currencies.values():
                if math.isnan(cs.current) or math.isinf(cs.current):
                    return self._build_report("Aborted: NaN/Inf detected")

        outcome = (
            "Terminal condition met"
            if self.terminal.is_met(state, self.context)
            else "Stall detected"
            if self.context.stall_detected
            else "Max iterations reached"
        )
        return self._build_report(outcome)

    def _build_report(self, outcome: str) -> SimulationReport:
        return build_report(
            collector=self.collector,
            strategy_description=self.strategy.describe(),
            terminal_description=self.terminal.describe(),
            outcome=outcome,
            total_time=self.runtime.get_state().time_elapsed,
        )
