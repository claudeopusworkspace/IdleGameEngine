from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from idleengine.report import SimulationReport


def export_csv(report: SimulationReport, path: str | Path) -> None:
    """Export simulation data as CSV files.

    Creates three files:
      - {path}_currencies.csv
      - {path}_purchases.csv
      - {path}_milestones.csv
    """
    base = str(path)

    # Currency series
    with open(f"{base}_currencies.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "currency_id", "value", "rate", "total_earned"])
        for s in report.currency_snapshots:
            writer.writerow([s.time, s.currency_id, s.value, s.rate, s.total_earned])

    # Purchases
    with open(f"{base}_purchases.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "element_id", "cost_json", "currencies_after_json"])
        for p in report.purchases:
            writer.writerow([
                p.time,
                p.element_id,
                json.dumps(p.cost_paid),
                json.dumps(p.currencies_after),
            ])

    # Milestones
    with open(f"{base}_milestones.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time", "milestone_id"])
        for m in report.milestones:
            writer.writerow([m.time, m.milestone_id])


def export_json(report: SimulationReport, path: str | Path) -> None:
    """Export full simulation report as JSON."""
    data = {
        "strategy": report.strategy_description,
        "terminal": report.terminal_description,
        "outcome": report.outcome,
        "total_time": report.total_time,
        "milestone_times": report.milestone_times,
        "purchase_count": len(report.purchases),
        "purchases_per_minute": report.purchases_per_minute,
        "max_purchase_gap": report.max_purchase_gap,
        "mean_purchase_gap": report.mean_purchase_gap,
        "dead_time_ratio": report.dead_time_ratio,
        "stall_count": len(report.stalls),
        "milestones": [
            {"time": m.time, "milestone_id": m.milestone_id}
            for m in report.milestones
        ],
        "purchases": [
            {
                "time": p.time,
                "element_id": p.element_id,
                "cost_paid": p.cost_paid,
            }
            for p in report.purchases
        ],
    }
    with open(str(path), "w") as f:
        json.dump(data, f, indent=2)
