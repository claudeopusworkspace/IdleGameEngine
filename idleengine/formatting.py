from __future__ import annotations

from idleengine.pacing import PacingBound, PacingBoundResult
from idleengine.report import SimulationReport


def format_text_report(
    report: SimulationReport,
    bounds: list[PacingBound] | None = None,
) -> str:
    """Format a simulation report for console output."""
    lines: list[str] = []

    lines.append("=" * 40 + " IdleEngine Simulation Report " + "=" * 40)
    lines.append(f"Strategy: {report.strategy_description}")
    lines.append(f"Terminal: {report.terminal_description}")
    lines.append(f"Result: {report.outcome} at {report.total_time:.1f}s")
    lines.append("")

    # Milestones
    if report.milestones:
        lines.append("MILESTONES:")
        for m in report.milestones:
            marker = "  *"
            time_str = f"{m.time:.1f}s"
            lines.append(f"{marker} {m.milestone_id:.<30s} {time_str}")
        lines.append("")

    # Purchase summary
    lines.append("PURCHASES:")
    lines.append(f"  Total: {len(report.purchases)}")
    lines.append(f"  Rate: {report.purchases_per_minute:.1f}/min")
    lines.append(f"  Max gap: {report.max_purchase_gap:.1f}s")
    lines.append(f"  Mean gap: {report.mean_purchase_gap:.1f}s")
    lines.append("")

    # Pacing bounds
    if bounds:
        lines.append("PACING:")
        errors = 0
        warnings = 0
        for bound in bounds:
            result = bound.evaluate(report)
            if result.passed:
                marker = "  [PASS]"
            elif bound.severity == "error":
                marker = "  [FAIL]"
                errors += 1
            else:
                marker = "  [WARN]"
                warnings += 1
            detail = result.message or bound.description
            lines.append(f"{marker} {detail}")
        lines.append("")

        if errors == 0 and warnings == 0:
            lines.append("SUMMARY: All bounds satisfied")
        else:
            parts = []
            if errors:
                parts.append(f"{errors} error(s)")
            if warnings:
                parts.append(f"{warnings} warning(s)")
            lines.append(f"SUMMARY: {', '.join(parts)} — NEEDS REBALANCING")

    return "\n".join(lines)
