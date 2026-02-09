"""Tests for pacing module."""
import pytest

from idleengine.metrics import MilestoneEvent, PurchaseEvent, StallEvent
from idleengine.pacing import PacingBound
from idleengine.report import SimulationReport


def _make_report(**kwargs) -> SimulationReport:
    defaults = dict(
        strategy_description="Test",
        terminal_description="Test",
        outcome="Done",
        total_time=1000.0,
        milestone_times={"first": 10.0, "second": 200.0},
        milestones=[
            MilestoneEvent(time=10.0, milestone_id="first"),
            MilestoneEvent(time=200.0, milestone_id="second"),
        ],
        purchases=[
            PurchaseEvent(time=5.0, element_id="a", cost_paid={}, currencies_after={}),
            PurchaseEvent(time=15.0, element_id="b", cost_paid={}, currencies_after={}),
            PurchaseEvent(time=50.0, element_id="c", cost_paid={}, currencies_after={}),
        ],
        purchase_gaps=[5.0, 10.0, 35.0],
        max_purchase_gap=35.0,
        mean_purchase_gap=16.67,
        dead_time_ratio=0.25,
        purchases_per_minute=0.18,
        stalls=[],
    )
    defaults.update(kwargs)
    return SimulationReport(**defaults)


def test_milestone_between_pass():
    bound = PacingBound.milestone_between("first", 5, 20)
    result = bound.evaluate(_make_report())
    assert result.passed


def test_milestone_between_fail():
    bound = PacingBound.milestone_between("first", 1, 5)
    result = bound.evaluate(_make_report())
    assert not result.passed  # first is at 10.0


def test_milestone_not_reached():
    bound = PacingBound.milestone_between("nonexistent", 1, 100)
    result = bound.evaluate(_make_report())
    assert not result.passed


def test_no_stalls_pass():
    bound = PacingBound.no_stalls()
    result = bound.evaluate(_make_report())
    assert result.passed


def test_no_stalls_fail():
    bound = PacingBound.no_stalls()
    report = _make_report(stalls=[StallEvent(time=100.0)])
    result = bound.evaluate(report)
    assert not result.passed


def test_dead_time_ratio_pass():
    bound = PacingBound.dead_time_ratio(max_ratio=0.30)
    result = bound.evaluate(_make_report())
    assert result.passed  # 0.25 <= 0.30


def test_dead_time_ratio_fail():
    bound = PacingBound.dead_time_ratio(max_ratio=0.10)
    result = bound.evaluate(_make_report())
    assert not result.passed  # 0.25 > 0.10


def test_custom():
    bound = PacingBound.custom(
        lambda r: r.total_time < 2000,
        "Game completable in 2000s",
    )
    result = bound.evaluate(_make_report())
    assert result.passed


def test_bound_detail():
    bound = PacingBound.milestone_between("first", 5, 20)
    result = bound.evaluate(_make_report())
    assert "first" in result.message
    assert "10.0" in result.message
