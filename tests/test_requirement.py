"""Tests for requirement module."""
import random

import pytest

from idleengine.requirement import Req, Requirement, EstimatedTimeRequirement
from idleengine.currency import CurrencyDef
from idleengine.definition import GameConfig, GameDefinition, ClickTarget
from idleengine.element import ElementDef
from idleengine.milestone import MilestoneDef
from idleengine.state import GameState


def _make_state() -> GameState:
    """Create a GameState with known values."""
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[
            CurrencyDef("gold", initial_value=500),
            CurrencyDef("gems", initial_value=10),
        ],
        elements=[
            ElementDef("farm"),
            ElementDef("mine"),
        ],
        milestones=[MilestoneDef("first")],
    )
    state = GameState(defn)
    state.currencies["gold"].current = 500
    state.currencies["gold"].total_earned = 1200
    state.elements["farm"].count = 5
    state.elements["mine"].count = 0
    state.time_elapsed = 120.0
    state.milestones_reached["first"] = 30.0
    return state


def test_resource():
    state = _make_state()
    assert Req.resource("gold", ">=", 500).evaluate(state)
    assert not Req.resource("gold", ">", 500).evaluate(state)
    assert Req.resource("gold", "<=", 500).evaluate(state)


def test_total_earned():
    state = _make_state()
    assert Req.total_earned("gold", ">=", 1000).evaluate(state)
    assert not Req.total_earned("gold", ">=", 2000).evaluate(state)


def test_owns():
    state = _make_state()
    assert Req.owns("farm").evaluate(state)
    assert not Req.owns("mine").evaluate(state)


def test_count():
    state = _make_state()
    assert Req.count("farm", ">=", 5).evaluate(state)
    assert not Req.count("farm", ">=", 6).evaluate(state)


def test_milestone():
    state = _make_state()
    assert Req.milestone("first").evaluate(state)
    assert not Req.milestone("nonexistent").evaluate(state)


def test_time():
    state = _make_state()
    assert Req.time(">=", 100).evaluate(state)
    assert not Req.time(">=", 200).evaluate(state)


def test_all():
    state = _make_state()
    r = Req.all(Req.resource("gold", ">=", 100), Req.owns("farm"))
    assert r.evaluate(state)

    r2 = Req.all(Req.resource("gold", ">=", 100), Req.owns("mine"))
    assert not r2.evaluate(state)


def test_any():
    state = _make_state()
    r = Req.any(Req.resource("gold", ">=", 9999), Req.owns("farm"))
    assert r.evaluate(state)

    r2 = Req.any(Req.resource("gold", ">=", 9999), Req.owns("mine"))
    assert not r2.evaluate(state)


def test_custom():
    state = _make_state()
    r = Req.custom(lambda s: s.element_count("farm") > 3)
    assert r.evaluate(state)


def test_and_or_operators():
    state = _make_state()
    r = Req.resource("gold", ">=", 100) & Req.owns("farm")
    assert r.evaluate(state)

    r2 = Req.resource("gold", ">=", 9999) | Req.owns("farm")
    assert r2.evaluate(state)


def test_estimated_time():
    state = _make_state()
    req = Req.estimated_time(mean=60.0, variance=0.0)
    # time_elapsed is 120, so should be met
    assert req.evaluate(state)

    req2 = Req.estimated_time(mean=200.0, variance=0.0)
    assert not req2.evaluate(state)


def test_estimated_time_with_rng():
    rng = random.Random(42)
    req = Req.estimated_time(mean=100.0, variance=10.0)
    req.inject_rng(rng)
    # The sampled time will be deterministic
    sampled = req.sample()
    assert 50.0 < sampled < 150.0

    # Reset and re-evaluate
    req.reset()
    req.inject_rng(random.Random(42))
