"""Tests for simulation module."""
import pytest

from idleengine.cost_scaling import CostScaling
from idleengine.currency import CurrencyDef
from idleengine.definition import ClickTarget, GameConfig, GameDefinition
from idleengine.effect import Effect, EffectType
from idleengine.element import ElementDef
from idleengine.milestone import MilestoneDef
from idleengine.requirement import Req
from idleengine.simulation import Simulation
from idleengine.strategy import ClickProfile, GreedyCheapest
from idleengine.terminal import Terminal


def _simple_game() -> GameDefinition:
    return GameDefinition(
        config=GameConfig(name="SimpleTest"),
        currencies=[CurrencyDef("gold", initial_value=0)],
        elements=[
            ElementDef(
                id="miner",
                base_cost={"gold": 10},
                cost_scaling=CostScaling.exponential(1.5),
                effects=[
                    Effect.per_count("miner", EffectType.PRODUCTION_FLAT, "gold", 2.0),
                ],
            ),
        ],
        milestones=[
            MilestoneDef(
                "first_miner",
                "First miner",
                trigger=Req.owns("miner"),
            ),
        ],
        click_targets=[ClickTarget("gold", base_value=1.0)],
    )


def test_tick_mode():
    defn = _simple_game()
    strategy = GreedyCheapest(
        click_profile=ClickProfile(targets={"gold": 5.0})
    )
    terminal = Terminal.time(120)

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        tick_resolution=1.0,
        seed=42,
    )
    report = sim.run()

    assert report.total_time >= 120.0
    assert report.outcome == "Terminal condition met"
    assert len(report.purchases) > 0
    # Should have reached first_miner milestone
    assert "first_miner" in report.milestone_times


def test_event_jump_mode():
    defn = _simple_game()
    strategy = GreedyCheapest(
        click_profile=ClickProfile(
            targets={"gold": 5.0},
            active_during_wait=True,
        )
    )
    terminal = Terminal.time(120)

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        tick_resolution=1.0,
        seed=42,
        mode="event_jump",
    )
    report = sim.run()

    assert report.total_time >= 120.0
    assert len(report.purchases) > 0
    assert "first_miner" in report.milestone_times


def test_milestone_terminal():
    defn = _simple_game()
    strategy = GreedyCheapest(
        click_profile=ClickProfile(targets={"gold": 10.0})
    )
    terminal = Terminal.any(
        Terminal.milestone("first_miner"),
        Terminal.time(300),
    )

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        tick_resolution=1.0,
        seed=42,
    )
    report = sim.run()

    # Should reach first_miner before 300s
    assert "first_miner" in report.milestone_times
    assert report.milestone_times["first_miner"] < 300.0


def test_stall_detection_event_jump():
    """A game with no clicks and no income should stall."""
    defn = GameDefinition(
        config=GameConfig(name="StallTest"),
        currencies=[CurrencyDef("gold", initial_value=0)],
        elements=[
            ElementDef(
                id="expensive",
                base_cost={"gold": 1000},
                cost_scaling=CostScaling.fixed(),
                effects=[
                    Effect.per_count("expensive", EffectType.PRODUCTION_FLAT, "gold", 1.0),
                ],
            ),
        ],
    )
    strategy = GreedyCheapest()
    terminal = Terminal.time(100)

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        mode="event_jump",
        seed=42,
    )
    report = sim.run()

    assert len(report.stalls) > 0 or report.outcome == "Stall detected"


def test_report_has_purchase_gaps():
    defn = _simple_game()
    strategy = GreedyCheapest(
        click_profile=ClickProfile(targets={"gold": 5.0})
    )
    terminal = Terminal.time(60)

    sim = Simulation(
        definition=defn,
        strategy=strategy,
        terminal=terminal,
        tick_resolution=1.0,
        seed=42,
    )
    report = sim.run()

    if report.purchases:
        assert len(report.purchase_gaps) > 0
        assert report.max_purchase_gap >= 0
        assert report.purchases_per_minute > 0
