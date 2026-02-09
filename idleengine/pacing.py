from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from idleengine.report import SimulationReport


@dataclass
class PacingBoundResult:
    """Result of evaluating a pacing bound."""

    bound: PacingBound
    passed: bool
    actual_value: float | None = None
    message: str = ""


class PacingBound:
    """A pass/fail pacing check against a simulation report."""

    def __init__(
        self,
        description: str,
        condition: Callable[[SimulationReport], bool],
        severity: str = "error",
        detail: Callable[[SimulationReport], str] | None = None,
    ) -> None:
        self.description = description
        self.condition = condition
        self.severity = severity
        self.detail = detail

    def evaluate(self, report: SimulationReport) -> PacingBoundResult:
        passed = self.condition(report)
        message = ""
        if self.detail:
            message = self.detail(report)
        return PacingBoundResult(
            bound=self,
            passed=passed,
            message=message,
        )

    @staticmethod
    def milestone_between(
        milestone_id: str,
        min_sec: float,
        max_sec: float,
        severity: str = "error",
    ) -> PacingBound:
        _mid = milestone_id
        _min = min_sec
        _max = max_sec

        def _cond(report: SimulationReport) -> bool:
            t = report.milestone_time(_mid)
            if t is None:
                return False
            return _min <= t <= _max

        def _detail(report: SimulationReport) -> str:
            t = report.milestone_time(_mid)
            if t is None:
                return f"{_mid}: not reached [bound: {_min}-{_max}s]"
            status = "OK" if _min <= t <= _max else "FAIL"
            return f"{_mid}: {t:.1f}s [bound: {_min}-{_max}s] {status}"

        return PacingBound(
            description=f"{milestone_id} between {min_sec}-{max_sec}s",
            condition=_cond,
            severity=severity,
            detail=_detail,
        )

    @staticmethod
    def max_gap_between_purchases(
        max_sec: float,
        after_time: float = 0.0,
        severity: str = "warning",
    ) -> PacingBound:
        _max = max_sec
        _after = after_time

        def _cond(report: SimulationReport) -> bool:
            purchase_times = sorted(p.time for p in report.purchases)
            if not purchase_times:
                return True
            gaps: list[float] = []
            prev = 0.0
            for t in purchase_times:
                if t >= _after:
                    gaps.append(t - prev)
                prev = t
            if not gaps:
                return True
            return max(gaps) <= _max

        def _detail(report: SimulationReport) -> str:
            purchase_times = sorted(p.time for p in report.purchases)
            if not purchase_times:
                return f"Max purchase gap: N/A (no purchases)"
            gaps: list[float] = []
            prev = 0.0
            for t in purchase_times:
                if t >= _after:
                    gaps.append(t - prev)
                prev = t
            mg = max(gaps) if gaps else 0.0
            return f"Max purchase gap: {mg:.0f}s (limit: {_max:.0f}s after {_after:.0f}s)"

        return PacingBound(
            description=f"Max purchase gap <= {max_sec}s after {after_time}s",
            condition=_cond,
            severity=severity,
            detail=_detail,
        )

    @staticmethod
    def no_stalls(severity: str = "error") -> PacingBound:
        return PacingBound(
            description="No stalls detected",
            condition=lambda r: len(r.stalls) == 0,
            severity=severity,
            detail=lambda r: (
                "No stalls detected"
                if len(r.stalls) == 0
                else f"{len(r.stalls)} stall(s) detected"
            ),
        )

    @staticmethod
    def dead_time_ratio(
        max_ratio: float = 0.30,
        severity: str = "warning",
    ) -> PacingBound:
        _max = max_ratio

        return PacingBound(
            description=f"Dead time ratio <= {max_ratio:.0%}",
            condition=lambda r: r.dead_time_ratio <= _max,
            severity=severity,
            detail=lambda r: f"Dead time ratio: {r.dead_time_ratio:.2f} (limit: {_max:.2f})",
        )

    @staticmethod
    def custom(
        condition: Callable[[SimulationReport], bool],
        description: str,
        severity: str = "error",
    ) -> PacingBound:
        return PacingBound(
            description=description,
            condition=condition,
            severity=severity,
        )
