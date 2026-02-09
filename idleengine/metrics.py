from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from idleengine.state import GameState


@dataclass
class CurrencySnapshot:
    time: float
    currency_id: str
    value: float
    rate: float
    total_earned: float


@dataclass
class ElementSnapshot:
    time: float
    element_id: str
    count: int


@dataclass
class PurchaseEvent:
    time: float
    element_id: str
    cost_paid: dict[str, float]
    currencies_after: dict[str, float]


@dataclass
class MilestoneEvent:
    time: float
    milestone_id: str


@dataclass
class PrestigeEvent:
    time: float
    layer_id: str
    reward_amount: float
    run_duration: float


@dataclass
class StallEvent:
    time: float
    duration: float = 0.0


@dataclass
class WaitEvent:
    time: float
    duration: float


class MetricsCollector:
    """Collects simulation metrics at configurable intervals."""

    def __init__(self, snapshot_interval: float = 1.0) -> None:
        self.snapshot_interval = snapshot_interval
        self._last_snapshot_time: float = -1.0

        self.currency_snapshots: list[CurrencySnapshot] = []
        self.element_snapshots: list[ElementSnapshot] = []
        self.purchases: list[PurchaseEvent] = []
        self.milestones: list[MilestoneEvent] = []
        self.prestiges: list[PrestigeEvent] = []
        self.stalls: list[StallEvent] = []
        self.waits: list[WaitEvent] = []

    def record_tick(self, state: GameState) -> None:
        """Record a snapshot if enough time has passed."""
        if state.time_elapsed - self._last_snapshot_time >= self.snapshot_interval:
            self._take_snapshot(state)
            self._last_snapshot_time = state.time_elapsed

    def record_purchase(
        self,
        state: GameState,
        element_id: str,
        cost_paid: dict[str, float],
    ) -> None:
        currencies_after = {
            cid: cs.current for cid, cs in state.currencies.items()
        }
        self.purchases.append(
            PurchaseEvent(
                time=state.time_elapsed,
                element_id=element_id,
                cost_paid=cost_paid,
                currencies_after=currencies_after,
            )
        )

    def record_milestone(self, state: GameState, milestone_id: str) -> None:
        self.milestones.append(
            MilestoneEvent(time=state.time_elapsed, milestone_id=milestone_id)
        )

    def record_prestige(
        self,
        state: GameState,
        layer_id: str,
        reward_amount: float,
        run_duration: float,
    ) -> None:
        self.prestiges.append(
            PrestigeEvent(
                time=state.time_elapsed,
                layer_id=layer_id,
                reward_amount=reward_amount,
                run_duration=run_duration,
            )
        )

    def record_stall(self, state: GameState, duration: float = 0.0) -> None:
        self.stalls.append(StallEvent(time=state.time_elapsed, duration=duration))

    def record_wait(self, state: GameState, duration: float) -> None:
        self.waits.append(WaitEvent(time=state.time_elapsed, duration=duration))

    def _take_snapshot(self, state: GameState) -> None:
        for cid, cs in state.currencies.items():
            self.currency_snapshots.append(
                CurrencySnapshot(
                    time=state.time_elapsed,
                    currency_id=cid,
                    value=cs.current,
                    rate=cs.current_rate,
                    total_earned=cs.total_earned,
                )
            )
        for eid, es in state.elements.items():
            self.element_snapshots.append(
                ElementSnapshot(
                    time=state.time_elapsed,
                    element_id=eid,
                    count=es.count,
                )
            )
