"""Tests for effect module."""
import pytest

from idleengine.effect import Effect, EffectDef, EffectPhase, EffectType, DEFAULT_PHASE
from idleengine.requirement import Req
from idleengine.currency import CurrencyDef
from idleengine.definition import GameConfig, GameDefinition
from idleengine.element import ElementDef
from idleengine.state import GameState


def _make_state() -> GameState:
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[CurrencyDef("gold")],
        elements=[
            ElementDef("farm"),
            ElementDef("mine"),
        ],
    )
    state = GameState(defn)
    state.elements["farm"].count = 10
    state.elements["mine"].count = 3
    return state


def test_default_phase():
    eff = EffectDef(type=EffectType.PRODUCTION_FLAT, target="gold", value=5.0)
    assert eff.phase == EffectPhase.BASE


def test_custom_phase():
    eff = EffectDef(
        type=EffectType.PRODUCTION_FLAT,
        target="gold",
        value=5.0,
        phase=EffectPhase.BONUS_ADD,
    )
    assert eff.phase == EffectPhase.BONUS_ADD


def test_resolve_literal():
    state = _make_state()
    eff = EffectDef(type=EffectType.PRODUCTION_FLAT, target="gold", value=5.0)
    assert eff.resolve(state) == 5.0


def test_resolve_callable():
    state = _make_state()
    eff = EffectDef(
        type=EffectType.PRODUCTION_FLAT,
        target="gold",
        value=lambda s: s.element_count("farm") * 2,
    )
    assert eff.resolve(state) == 20.0


def test_is_active_no_condition():
    state = _make_state()
    eff = EffectDef(type=EffectType.PRODUCTION_FLAT, target="gold", value=1.0)
    assert eff.is_active(state)


def test_is_active_with_condition():
    state = _make_state()
    eff = EffectDef(
        type=EffectType.PRODUCTION_FLAT,
        target="gold",
        value=1.0,
        condition=Req.count("farm", ">=", 5),
    )
    assert eff.is_active(state)

    eff2 = EffectDef(
        type=EffectType.PRODUCTION_FLAT,
        target="gold",
        value=1.0,
        condition=Req.count("farm", ">=", 20),
    )
    assert not eff2.is_active(state)


def test_per_count():
    state = _make_state()
    eff = Effect.per_count("farm", EffectType.PRODUCTION_FLAT, "gold", 2.0)
    assert eff.resolve(state) == 20.0  # 10 farms * 2.0


def test_static():
    state = _make_state()
    eff = Effect.static(EffectType.PRODUCTION_MULT, "gold", 2.0)
    assert eff.resolve(state) == 2.0


def test_synergy():
    state = _make_state()
    eff = Effect.synergy("mine", EffectType.PRODUCTION_ADD_PCT, "gold", 0.01)
    assert eff.resolve(state) == pytest.approx(0.03)  # 3 mines * 0.01


def test_default_phase_mapping():
    # Verify all EffectTypes have a default phase
    for et in EffectType:
        assert et in DEFAULT_PHASE
