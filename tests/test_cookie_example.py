"""Integration test with the cookie example game."""
import sys
import os

import pytest

# Ensure examples can be imported
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from examples.cookie_example import define_game
from idleengine.formatting import format_text_report
from idleengine.simulation import Simulation
from idleengine.strategy import ClickProfile, GreedyCheapest
from idleengine.terminal import Terminal


def test_cookie_game_validates():
    defn = define_game()
    errors = defn.validate()
    assert errors == [], f"Validation errors: {errors}"


def test_cookie_game_simulation():
    defn = define_game()

    strategy = GreedyCheapest(
        click_profile=ClickProfile(targets={"cookies": 5.0})
    )
    terminal = Terminal.any(
        Terminal.time(7200),
        Terminal.milestone("million_cookies"),
    )

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        tick_resolution=1.0,
        seed=42,
    )
    report = sim.run()

    # Basic checks
    assert report.total_time > 0
    assert len(report.purchases) > 0

    # first_purchase should be reached quickly
    assert "first_purchase" in report.milestone_times
    fp_time = report.milestone_times["first_purchase"]
    assert 1 <= fp_time <= 60, f"first_purchase at {fp_time}s (expected 3-60s)"

    # hundred_cps should be reachable
    assert "hundred_cps" in report.milestone_times
    hcps_time = report.milestone_times["hundred_cps"]
    assert hcps_time > 0

    # No stalls
    assert len(report.stalls) == 0, "Unexpected stalls detected"


def test_cookie_game_report_output():
    defn = define_game()

    strategy = GreedyCheapest(
        click_profile=ClickProfile(targets={"cookies": 5.0})
    )
    terminal = Terminal.time(600)

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        tick_resolution=1.0,
        seed=42,
    )
    report = sim.run()

    text = format_text_report(report, defn.pacing_bounds)
    assert "IdleEngine Simulation Report" in text
    assert "Strategy:" in text
    assert "PURCHASES:" in text


def test_cookie_event_jump_mode():
    defn = define_game()

    strategy = GreedyCheapest(
        click_profile=ClickProfile(
            targets={"cookies": 5.0},
            active_during_wait=True,
        )
    )
    terminal = Terminal.time(600)

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        tick_resolution=1.0,
        seed=42,
        mode="event_jump",
    )
    report = sim.run()

    assert report.total_time > 0
    assert len(report.purchases) > 0
    # Should reach first_purchase
    assert "first_purchase" in report.milestone_times
