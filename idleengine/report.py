from __future__ import annotations

from dataclasses import dataclass, field

from idleengine.metrics import (
    MetricsCollector,
    CurrencySnapshot,
    PurchaseEvent,
    MilestoneEvent,
    PrestigeEvent,
    StallEvent,
)


@dataclass
class SimulationReport:
    """Container for simulation results and derived metrics."""

    strategy_description: str = ""
    terminal_description: str = ""
    outcome: str = ""
    total_time: float = 0.0

    # Raw metrics
    currency_snapshots: list[CurrencySnapshot] = field(default_factory=list)
    purchases: list[PurchaseEvent] = field(default_factory=list)
    milestones: list[MilestoneEvent] = field(default_factory=list)
    prestiges: list[PrestigeEvent] = field(default_factory=list)
    stalls: list[StallEvent] = field(default_factory=list)

    # Derived metrics
    milestone_times: dict[str, float] = field(default_factory=dict)
    purchase_gaps: list[float] = field(default_factory=list)
    max_purchase_gap: float = 0.0
    mean_purchase_gap: float = 0.0
    dead_time_ratio: float = 0.0
    purchases_per_minute: float = 0.0

    def milestone_time(self, milestone_id: str) -> float | None:
        return self.milestone_times.get(milestone_id)

    def currency_series(self, currency_id: str) -> list[tuple[float, float]]:
        """Return (time, value) series for a currency."""
        return [
            (s.time, s.value)
            for s in self.currency_snapshots
            if s.currency_id == currency_id
        ]

    def rate_series(self, currency_id: str) -> list[tuple[float, float]]:
        """Return (time, rate) series for a currency."""
        return [
            (s.time, s.rate)
            for s in self.currency_snapshots
            if s.currency_id == currency_id
        ]


def build_report(
    collector: MetricsCollector,
    strategy_description: str,
    terminal_description: str,
    outcome: str,
    total_time: float,
) -> SimulationReport:
    """Build a SimulationReport from collected metrics."""
    # Milestone times
    milestone_times = {m.milestone_id: m.time for m in collector.milestones}

    # Purchase gaps
    purchase_gaps: list[float] = []
    purchase_times = sorted(p.time for p in collector.purchases)
    if purchase_times:
        purchase_gaps.append(purchase_times[0])  # gap from t=0 to first purchase
        for i in range(1, len(purchase_times)):
            purchase_gaps.append(purchase_times[i] - purchase_times[i - 1])

    max_gap = max(purchase_gaps) if purchase_gaps else 0.0
    mean_gap = (sum(purchase_gaps) / len(purchase_gaps)) if purchase_gaps else 0.0

    # Dead time ratio: time spent in waits vs total time
    total_wait = sum(w.duration for w in collector.waits)
    dead_ratio = total_wait / total_time if total_time > 0 else 0.0

    # Purchases per minute
    ppm = (len(collector.purchases) / total_time * 60.0) if total_time > 0 else 0.0

    return SimulationReport(
        strategy_description=strategy_description,
        terminal_description=terminal_description,
        outcome=outcome,
        total_time=total_time,
        currency_snapshots=collector.currency_snapshots,
        purchases=collector.purchases,
        milestones=collector.milestones,
        prestiges=collector.prestiges,
        stalls=collector.stalls,
        milestone_times=milestone_times,
        purchase_gaps=purchase_gaps,
        max_purchase_gap=max_gap,
        mean_purchase_gap=mean_gap,
        dead_time_ratio=dead_ratio,
        purchases_per_minute=ppm,
    )
