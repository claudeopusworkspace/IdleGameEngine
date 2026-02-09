"""Tests for state module."""
import pytest

from idleengine.currency import CurrencyDef
from idleengine.definition import GameConfig, GameDefinition
from idleengine.element import ElementDef
from idleengine.milestone import MilestoneDef
from idleengine.prestige import PrestigeLayerDef
from idleengine.state import GameState


def _make_definition() -> GameDefinition:
    return GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[
            CurrencyDef("gold", initial_value=100),
            CurrencyDef("gems", initial_value=5),
        ],
        elements=[
            ElementDef("farm"),
            ElementDef("mine"),
        ],
        milestones=[MilestoneDef("first")],
        prestige_layers=[PrestigeLayerDef(id="prestige", prestige_currency="gems")],
    )


def test_initialization():
    state = GameState(_make_definition())
    assert state.time_elapsed == 0.0
    assert state.run_number == 1
    assert "gold" in state.currencies
    assert "gems" in state.currencies
    assert "farm" in state.elements
    assert "mine" in state.elements


def test_currency_initial_values():
    state = GameState(_make_definition())
    assert state.currency_value("gold") == 100
    assert state.currency_value("gems") == 5


def test_currency_value_unknown():
    state = GameState(_make_definition())
    assert state.currency_value("nonexistent") == 0.0


def test_element_count():
    state = GameState(_make_definition())
    assert state.element_count("farm") == 0
    state.elements["farm"].count = 5
    assert state.element_count("farm") == 5


def test_element_count_unknown():
    state = GameState(_make_definition())
    assert state.element_count("nonexistent") == 0


def test_has_milestone():
    state = GameState(_make_definition())
    assert not state.has_milestone("first")
    state.milestones_reached["first"] = 10.0
    assert state.has_milestone("first")


def test_total_earned():
    state = GameState(_make_definition())
    assert state.total_earned("gold") == 100  # initial value counts
    state.currencies["gold"].total_earned = 5000
    assert state.total_earned("gold") == 5000


def test_prestige_counts():
    state = GameState(_make_definition())
    assert state.prestige_counts.get("prestige") == 0
