"""Tests for runtime module."""
import pytest

from idleengine.cost_scaling import CostScaling
from idleengine.currency import CurrencyDef
from idleengine.definition import ClickTarget, GameConfig, GameDefinition
from idleengine.effect import Effect, EffectDef, EffectType
from idleengine.element import ElementDef
from idleengine.milestone import MilestoneDef
from idleengine.prestige import PrestigeLayerDef
from idleengine.requirement import Req
from idleengine.runtime import GameRuntime


def _make_simple_game() -> GameDefinition:
    """A minimal game for testing runtime."""
    return GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[
            CurrencyDef("gold", initial_value=1000),
        ],
        elements=[
            ElementDef(
                id="miner",
                display_name="Miner",
                base_cost={"gold": 100},
                cost_scaling=CostScaling.fixed(),
                effects=[
                    Effect.per_count("miner", EffectType.PRODUCTION_FLAT, "gold", 5.0),
                ],
            ),
            ElementDef(
                id="doubler",
                display_name="Doubler",
                base_cost={"gold": 500},
                cost_scaling=CostScaling.fixed(),
                max_count=1,
                effects=[
                    Effect.static(EffectType.PRODUCTION_MULT, "gold", 2.0),
                ],
                requirements=[Req.count("miner", ">=", 3)],
            ),
        ],
        milestones=[
            MilestoneDef(
                "first_miner",
                "Got first miner",
                trigger=Req.owns("miner"),
            ),
        ],
        click_targets=[ClickTarget("gold", base_value=1.0)],
    )


def test_initialization():
    rt = GameRuntime(_make_simple_game())
    state = rt.get_state()
    assert state.currency_value("gold") == 1000
    assert state.element_count("miner") == 0


def test_purchase():
    rt = GameRuntime(_make_simple_game())
    assert rt.try_purchase("miner")
    assert rt.get_state().element_count("miner") == 1
    assert rt.get_state().currency_value("gold") == 900


def test_purchase_too_expensive():
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[CurrencyDef("gold", initial_value=50)],
        elements=[
            ElementDef(
                id="miner",
                base_cost={"gold": 100},
                cost_scaling=CostScaling.fixed(),
            ),
        ],
    )
    rt = GameRuntime(defn)
    rt.tick(0)  # update statuses
    assert not rt.try_purchase("miner")


def test_purchase_max_count():
    rt = GameRuntime(_make_simple_game())
    # Buy doubler prerequisite (3 miners)
    for _ in range(3):
        rt.try_purchase("miner")
    rt.tick(0)  # update availability
    assert rt.try_purchase("doubler")
    assert not rt.try_purchase("doubler")  # max_count=1


def test_tick_production():
    rt = GameRuntime(_make_simple_game())
    rt.try_purchase("miner")
    # After purchase: miner.count=1, rate should be 5/sec
    rt.tick(10.0)
    state = rt.get_state()
    # 900 - 0 (already deducted) + 5 * 10 = 950
    assert state.currency_value("gold") == pytest.approx(950.0)


def test_tick_with_multiplier():
    rt = GameRuntime(_make_simple_game())
    # Buy 3 miners
    for _ in range(3):
        rt.try_purchase("miner")
    rt.tick(0)  # update availability for doubler
    rt.try_purchase("doubler")
    # miners produce 15/sec (3 * 5), doubler makes it 30/sec
    rt.tick(1.0)
    state = rt.get_state()
    # Starting: 1000 - 300 (miners) - 500 (doubler) = 200
    # After 1s: 200 + 30 = 230
    assert state.currency_value("gold") == pytest.approx(230.0)


def test_click():
    rt = GameRuntime(_make_simple_game())
    amount = rt.process_click("gold")
    assert amount == pytest.approx(1.0)
    assert rt.get_state().currency_value("gold") == pytest.approx(1001.0)


def test_milestone_fires():
    rt = GameRuntime(_make_simple_game())
    assert not rt.get_state().has_milestone("first_miner")
    rt.try_purchase("miner")
    rt.tick(0)  # trigger milestone check
    assert rt.get_state().has_milestone("first_miner")


def test_element_availability():
    rt = GameRuntime(_make_simple_game())
    rt.tick(0)  # initial status update
    # Doubler requires 3 miners
    avail = rt.get_available_purchases()
    avail_ids = {e.id for e in avail}
    assert "miner" in avail_ids
    assert "doubler" not in avail_ids

    for _ in range(3):
        rt.try_purchase("miner")
    rt.tick(0)

    avail = rt.get_available_purchases()
    avail_ids = {e.id for e in avail}
    assert "doubler" in avail_ids


def test_affordable_purchases():
    rt = GameRuntime(_make_simple_game())
    rt.tick(0)
    affordable = rt.get_affordable_purchases()
    affordable_ids = {e.id for e in affordable}
    assert "miner" in affordable_ids


def test_compute_time_to_afford():
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[CurrencyDef("gold", initial_value=0)],
        elements=[
            ElementDef(
                id="cheap",
                base_cost={"gold": 50},
                cost_scaling=CostScaling.fixed(),
                effects=[
                    Effect.per_count("cheap", EffectType.PRODUCTION_FLAT, "gold", 10.0),
                ],
            ),
        ],
    )
    rt = GameRuntime(defn)
    rt.try_purchase("cheap")  # free because we have 0 gold? No, cost is 50
    # Can't afford it
    rt.tick(0)
    # Rate is 0, so time_to_afford should be None
    t = rt.compute_time_to_afford("cheap")
    assert t is None


def test_prestige():
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[
            CurrencyDef("gold", initial_value=1_000_000),
            CurrencyDef("prestige_pts", initial_value=0, persistent=True),
        ],
        elements=[
            ElementDef("miner", base_cost={"gold": 100}, cost_scaling=CostScaling.fixed()),
        ],
        prestige_layers=[
            PrestigeLayerDef(
                id="prestige",
                prestige_currency="prestige_pts",
                reward_formula=lambda s: 10.0,
                currencies_reset=["gold"],
                elements_reset=["miner"],
                requirements=[Req.resource("gold", ">=", 100000)],
                minimum_reward=1.0,
            ),
        ],
    )
    rt = GameRuntime(defn)
    # Buy a miner first
    rt.try_purchase("miner")
    rt.tick(0)

    result = rt.trigger_prestige("prestige")
    assert result.success
    assert result.reward_amount == 10.0
    assert rt.get_state().currency_value("prestige_pts") == 10.0
    # Gold resets to its initial_value (1_000_000)
    assert rt.get_state().currency_value("gold") == 1_000_000
    assert rt.get_state().element_count("miner") == 0


def test_prestige_requirements_not_met():
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[
            CurrencyDef("gold", initial_value=100),
            CurrencyDef("prestige_pts", initial_value=0, persistent=True),
        ],
        elements=[],
        prestige_layers=[
            PrestigeLayerDef(
                id="prestige",
                prestige_currency="prestige_pts",
                reward_formula=lambda s: 10.0,
                currencies_reset=["gold"],
                elements_reset=[],
                requirements=[Req.resource("gold", ">=", 100000)],
                minimum_reward=1.0,
            ),
        ],
    )
    rt = GameRuntime(defn)
    result = rt.trigger_prestige("prestige")
    assert not result.success


def test_invalid_definition():
    defn = GameDefinition(
        config=GameConfig(name="Test"),
        currencies=[],
        elements=[
            ElementDef("bad", base_cost={"nonexistent": 100}, cost_scaling=CostScaling.fixed()),
        ],
    )
    with pytest.raises(ValueError, match="Invalid GameDefinition"):
        GameRuntime(defn)
