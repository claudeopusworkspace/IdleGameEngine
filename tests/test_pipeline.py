"""Tests for pipeline module."""
import pytest

from idleengine.effect import EffectType
from idleengine.pipeline import ProductionPipeline
from idleengine.currency import CurrencyDef
from idleengine.definition import GameConfig, GameDefinition
from idleengine.state import GameState


def _make_state() -> GameState:
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[CurrencyDef("gold")],
    )
    return GameState(defn)


def test_flat_only():
    p = ProductionPipeline()
    effects = [
        (EffectType.PRODUCTION_FLAT, 5.0),
        (EffectType.PRODUCTION_FLAT, 3.0),
    ]
    rate = p.compute_rate("gold", effects, _make_state())
    assert rate == pytest.approx(8.0)


def test_flat_with_add_pct():
    p = ProductionPipeline()
    effects = [
        (EffectType.PRODUCTION_FLAT, 10.0),
        (EffectType.PRODUCTION_ADD_PCT, 0.5),  # +50%
    ]
    rate = p.compute_rate("gold", effects, _make_state())
    assert rate == pytest.approx(15.0)  # 10 * (1 + 0.5)


def test_full_pipeline():
    p = ProductionPipeline()
    effects = [
        (EffectType.PRODUCTION_FLAT, 10.0),
        (EffectType.PRODUCTION_ADD_PCT, 0.5),   # +50%
        (EffectType.PRODUCTION_MULT, 2.0),       # x2
        (EffectType.GLOBAL_MULT, 3.0),           # x3
    ]
    rate = p.compute_rate("gold", effects, _make_state())
    # 10 * (1 + 0.5) * 2 * 3 = 90
    assert rate == pytest.approx(90.0)


def test_multiple_multipliers():
    p = ProductionPipeline()
    effects = [
        (EffectType.PRODUCTION_FLAT, 10.0),
        (EffectType.PRODUCTION_MULT, 2.0),
        (EffectType.PRODUCTION_MULT, 3.0),
    ]
    rate = p.compute_rate("gold", effects, _make_state())
    # 10 * 1.0 * (2 * 3) * 1.0 = 60
    assert rate == pytest.approx(60.0)


def test_no_effects():
    p = ProductionPipeline()
    rate = p.compute_rate("gold", [], _make_state())
    assert rate == pytest.approx(0.0)


def test_click_value():
    p = ProductionPipeline()
    effects = [
        (EffectType.CLICK_FLAT, 5.0),
        (EffectType.CLICK_MULT, 2.0),
    ]
    val = p.compute_click_value("gold", 1.0, effects, _make_state())
    # (1.0 + 5.0) * 2.0 = 12.0
    assert val == pytest.approx(12.0)


def test_click_value_no_effects():
    p = ProductionPipeline()
    val = p.compute_click_value("gold", 1.0, [], _make_state())
    assert val == pytest.approx(1.0)


def test_custom_pipeline():
    p = ProductionPipeline()
    p.set_custom("gold", lambda cid, effects, state: 42.0)
    rate = p.compute_rate("gold", [], _make_state())
    assert rate == pytest.approx(42.0)
