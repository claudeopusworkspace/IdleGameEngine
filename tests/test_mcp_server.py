"""Tests for MCP server tool functions."""

import pytest

from idleengine.cost_scaling import CostScaling
from idleengine.currency import CurrencyDef
from idleengine.definition import ClickTarget, GameConfig, GameDefinition
from idleengine.effect import Effect, EffectType
from idleengine.element import ElementDef
from idleengine.milestone import MilestoneDef
from idleengine.prestige import PrestigeLayerDef
from idleengine.requirement import Req
from idleengine.runtime import GameRuntime

from idleengine.mcp.server import (
    _GameHolder,
    _compute_effective_rate,
    _tool_click,
    _tool_get_available_purchases,
    _tool_get_element_info,
    _tool_get_game_info,
    _tool_get_game_state,
    _tool_new_game,
    _tool_prestige,
    _tool_purchase,
    _tool_set_click_rate,
    _tool_wait,
)


def _make_test_definition() -> GameDefinition:
    """A small but complete game definition for testing."""
    return GameDefinition(
        config=GameConfig(name="Test Game"),
        currencies=[
            CurrencyDef("gold", display_name="Gold", initial_value=100),
            CurrencyDef("gems", display_name="Gems", initial_value=0, persistent=True),
        ],
        elements=[
            ElementDef(
                id="miner",
                display_name="Miner",
                description="Produces gold",
                base_cost={"gold": 10},
                cost_scaling=CostScaling.fixed(),
                effects=[
                    Effect.per_count("miner", EffectType.PRODUCTION_FLAT, "gold", 1.0),
                ],
                category="production",
            ),
            ElementDef(
                id="rare_gem",
                display_name="Rare Gem",
                base_cost={"gold": 500},
                cost_scaling=CostScaling.fixed(),
                max_count=1,
                requirements=[Req.count("miner", ">=", 5)],
                category="upgrades",
            ),
        ],
        milestones=[
            MilestoneDef(
                id="first_miner",
                description="Buy your first miner",
                trigger=Req.owns("miner"),
            ),
            MilestoneDef(
                id="gold_100",
                description="Reach 100 gold",
                trigger=Req.resource("gold", ">=", 100),
            ),
        ],
        click_targets=[ClickTarget("gold", base_value=1.0)],
        prestige_layers=[
            PrestigeLayerDef(
                id="rebirth",
                prestige_currency="gems",
                reward_formula=lambda s: 5.0,
                currencies_reset=["gold"],
                elements_reset=["miner", "rare_gem"],
                requirements=[Req.resource("gold", ">=", 1000)],
                minimum_reward=1.0,
            ),
        ],
    )


def _make_holder() -> _GameHolder:
    defn = _make_test_definition()
    return _GameHolder(
        definition=defn,
        runtime=GameRuntime(defn),
    )


# ── get_game_info ────────────────────────────────────────────────────


class TestGetGameInfo:
    def test_returns_expected_structure(self):
        holder = _make_holder()
        result = _tool_get_game_info(holder)
        assert result["name"] == "Test Game"
        assert len(result["currencies"]) == 2
        assert len(result["elements"]) == 2
        assert len(result["milestones"]) == 2
        assert len(result["click_targets"]) == 1
        assert len(result["prestige_layers"]) == 1

    def test_currency_ids(self):
        holder = _make_holder()
        result = _tool_get_game_info(holder)
        ids = [c["id"] for c in result["currencies"]]
        assert "gold" in ids
        assert "gems" in ids

    def test_element_categories(self):
        holder = _make_holder()
        result = _tool_get_game_info(holder)
        elements = {e["id"]: e for e in result["elements"]}
        assert elements["miner"]["category"] == "production"
        assert elements["rare_gem"]["category"] == "upgrades"


# ── get_game_state ───────────────────────────────────────────────────


class TestGetGameState:
    def test_initial_values(self):
        holder = _make_holder()
        result = _tool_get_game_state(holder)
        assert result["time_elapsed"] == 0.0
        assert result["currencies"]["gold"]["current"] == 100.0
        assert result["currencies"]["gems"]["current"] == 0.0
        assert result["elements"]["miner"]["count"] == 0
        assert result["milestones_reached"] == []
        assert result["run_number"] == 1

    def test_after_purchase(self):
        holder = _make_holder()
        holder.runtime.try_purchase("miner")
        holder.runtime.tick(0)
        result = _tool_get_game_state(holder)
        assert result["currencies"]["gold"]["current"] == 90.0
        assert result["elements"]["miner"]["count"] == 1


# ── purchase ─────────────────────────────────────────────────────────


class TestPurchase:
    def test_success(self):
        holder = _make_holder()
        result = _tool_purchase(holder, "miner")
        assert result["success"] is True
        assert result["new_count"] == 1

    def test_rates_update_immediately(self):
        """Rates should reflect the purchase without needing a wait() first."""
        holder = _make_holder()
        _tool_purchase(holder, "miner")
        state = _tool_get_game_state(holder)
        # 1 miner producing 1.0 gold/sec — rate should already be visible
        assert state["currencies"]["gold"]["rate"] == 1.0

    def test_cannot_afford(self):
        holder = _make_holder()
        # Spend all gold buying miners (100 gold, 10 per miner = 10 miners)
        for _ in range(10):
            holder.runtime.try_purchase("miner")
        result = _tool_purchase(holder, "miner")
        assert result["success"] is False
        assert "afford" in result["reason"].lower()

    def test_unknown_element(self):
        holder = _make_holder()
        result = _tool_purchase(holder, "nonexistent")
        assert "error" in result

    def test_max_count(self):
        holder = _make_holder()
        # Need 5 miners for rare_gem
        for _ in range(5):
            holder.runtime.try_purchase("miner")
        holder.runtime.tick(0)
        # Earn gold to afford rare_gem (500 gold needed)
        # We have 100 - 50 = 50, need to wait
        for _ in range(500):
            holder.runtime.tick(1.0)
        result = _tool_purchase(holder, "rare_gem")
        assert result["success"] is True
        # Try again - max_count=1
        result = _tool_purchase(holder, "rare_gem")
        assert result["success"] is False
        assert "max" in result["reason"].lower()

    def test_not_available(self):
        holder = _make_holder()
        # rare_gem requires 5 miners
        result = _tool_purchase(holder, "rare_gem")
        assert result["success"] is False
        assert "not available" in result["reason"].lower()


# ── click ────────────────────────────────────────────────────────────


class TestClick:
    def test_valid_click(self):
        holder = _make_holder()
        result = _tool_click(holder, "gold", 1)
        assert result["clicks"] == 1
        assert result["total_earned"] == 1.0
        assert result["new_balance"] == 101.0

    def test_multiple_clicks(self):
        holder = _make_holder()
        result = _tool_click(holder, "gold", 10)
        assert result["clicks"] == 10
        assert result["total_earned"] == 10.0
        assert result["new_balance"] == 110.0

    def test_invalid_target(self):
        holder = _make_holder()
        result = _tool_click(holder, "nonexistent")
        assert "error" in result

    def test_count_too_low(self):
        holder = _make_holder()
        result = _tool_click(holder, "gold", 0)
        assert "error" in result

    def test_count_too_high(self):
        holder = _make_holder()
        result = _tool_click(holder, "gold", 9999)
        assert "error" in result


# ── wait ─────────────────────────────────────────────────────────────


class TestWait:
    def test_basic_wait(self):
        holder = _make_holder()
        holder.runtime.try_purchase("miner")
        holder.runtime.tick(0)  # update rates
        result = _tool_wait(holder, 10)
        assert result["waited"] == 10
        assert result["time_elapsed"] == 10.0
        # 1 miner * 1.0/sec * 10s = 10 gold earned
        assert result["currencies"]["gold"]["current"] == 100.0  # 90 + 10

    def test_subdivision_triggers_milestones(self):
        """wait() subdivides into 1s ticks, so milestones fire mid-wait."""
        holder = _make_holder()
        # Buy a miner - should trigger first_miner milestone on next tick
        holder.runtime.try_purchase("miner")
        # Wait - milestone should fire during the subdivided ticks
        result = _tool_wait(holder, 5)
        assert "new_milestones" in result
        assert "first_miner" in result["new_milestones"]

    def test_negative_seconds(self):
        holder = _make_holder()
        result = _tool_wait(holder, -1)
        assert "error" in result

    def test_exceeds_max(self):
        holder = _make_holder()
        result = _tool_wait(holder, 100000)
        assert "error" in result

    def test_milestone_already_reached(self):
        """gold_100 milestone fires immediately (initial gold=100)."""
        holder = _make_holder()
        # gold_100 triggers at >=100 gold, we start with 100
        result = _tool_wait(holder, 1)
        assert "new_milestones" in result
        assert "gold_100" in result["new_milestones"]
        # Wait again - should NOT report it again
        result2 = _tool_wait(holder, 1)
        if "new_milestones" in result2:
            assert "gold_100" not in result2["new_milestones"]


# ── prestige ─────────────────────────────────────────────────────────


class TestPrestige:
    def test_success(self):
        holder = _make_holder()
        # Need >=1000 gold. Start with 100. Buy miners and wait.
        for _ in range(5):
            holder.runtime.try_purchase("miner")
        # Now have 50 gold, 5 miners at 1/sec each = 5/sec
        # Need 950 more gold -> 190 seconds
        for _ in range(200):
            holder.runtime.tick(1.0)
        assert holder.runtime.get_state().currency_value("gold") >= 1000
        result = _tool_prestige(holder, "rebirth")
        assert result["success"] is True
        assert result["reward_amount"] == 5.0

    def test_requirements_not_met(self):
        holder = _make_holder()
        result = _tool_prestige(holder, "rebirth")
        assert result["success"] is False
        assert "not met" in result["reason"].lower()

    def test_unknown_layer(self):
        holder = _make_holder()
        result = _tool_prestige(holder, "nonexistent")
        assert "error" in result


# ── new_game ─────────────────────────────────────────────────────────


class TestNewGame:
    def test_resets_state(self):
        holder = _make_holder()
        # Mutate state
        holder.runtime.try_purchase("miner")
        holder.runtime.tick(10)
        assert holder.runtime.get_state().element_count("miner") == 1
        assert holder.runtime.get_state().time_elapsed > 0

        # Reset
        result = _tool_new_game(holder)
        assert result["success"] is True
        assert holder.runtime.get_state().element_count("miner") == 0
        assert holder.runtime.get_state().time_elapsed == 0.0
        assert holder.runtime.get_state().currency_value("gold") == 100.0

    def test_clears_milestone_tracking(self):
        holder = _make_holder()
        holder.runtime.try_purchase("miner")
        _tool_wait(holder, 1)
        assert len(holder._milestones_seen) > 0
        _tool_new_game(holder)
        assert len(holder._milestones_seen) == 0


# ── get_available_purchases ──────────────────────────────────────────


class TestGetAvailablePurchases:
    def test_initial(self):
        holder = _make_holder()
        result = _tool_get_available_purchases(holder)
        ids = [p["id"] for p in result["purchases"]]
        assert "miner" in ids
        assert "rare_gem" not in ids  # requires 5 miners

    def test_includes_time_to_afford(self):
        holder = _make_holder()
        result = _tool_get_available_purchases(holder)
        miner = next(p for p in result["purchases"] if p["id"] == "miner")
        # Miner costs 10, we have 100 -> already affordable
        assert miner["affordable"] is True
        assert miner["time_to_afford"] == 0.0

    def test_time_to_afford_with_rate(self):
        holder = _make_holder()
        # Buy 9 miners to almost exhaust gold
        for _ in range(9):
            holder.runtime.try_purchase("miner")
        holder.runtime.tick(0)
        result = _tool_get_available_purchases(holder)
        miner = next(p for p in result["purchases"] if p["id"] == "miner")
        # 10 gold left, cost=10 -> affordable
        assert miner["affordable"] is True


# ── get_element_info ─────────────────────────────────────────────────


class TestGetElementInfo:
    def test_valid_element(self):
        holder = _make_holder()
        result = _tool_get_element_info(holder, "miner")
        assert result["id"] == "miner"
        assert result["display_name"] == "Miner"
        assert result["description"] == "Produces gold"
        assert result["category"] == "production"
        assert result["count"] == 0
        assert "current_cost" in result
        assert result["current_cost"]["gold"] == 10.0
        assert len(result["effects"]) == 1
        assert result["effects"][0]["type"] == "PRODUCTION_FLAT"

    def test_unknown_element(self):
        holder = _make_holder()
        result = _tool_get_element_info(holder, "nonexistent")
        assert "error" in result

    def test_shows_max_count(self):
        holder = _make_holder()
        result = _tool_get_element_info(holder, "rare_gem")
        assert result["max_count"] == 1

    def test_no_max_count_key_when_none(self):
        holder = _make_holder()
        result = _tool_get_element_info(holder, "miner")
        assert "max_count" not in result


# ── set_click_rate ───────────────────────────────────────────────────


class TestSetClickRate:
    def test_set_valid_rate(self):
        holder = _make_holder()
        result = _tool_set_click_rate(holder, "gold", 5.0)
        assert result["target"] == "gold"
        assert result["cps"] == 5.0
        assert result["active_click_rates"] == {"gold": 5.0}

    def test_set_zero_clears(self):
        holder = _make_holder()
        _tool_set_click_rate(holder, "gold", 5.0)
        result = _tool_set_click_rate(holder, "gold", 0)
        assert result["active_click_rates"] == {}
        assert "gold" not in holder._click_rates

    def test_invalid_target(self):
        holder = _make_holder()
        result = _tool_set_click_rate(holder, "nonexistent", 1.0)
        assert "error" in result

    def test_negative_cps(self):
        holder = _make_holder()
        result = _tool_set_click_rate(holder, "gold", -1.0)
        assert "error" in result

    def test_clicks_applied_during_wait(self):
        holder = _make_holder()
        # No production, just clicking at 5 cps for 10s = 50 clicks = 50 gold
        _tool_set_click_rate(holder, "gold", 5.0)
        result = _tool_wait(holder, 10)
        # Started with 100, 50 clicks * 1.0 base_value = 50 added
        assert result["currencies"]["gold"]["current"] == 150.0

    def test_click_rate_shown_in_state(self):
        holder = _make_holder()
        _tool_set_click_rate(holder, "gold", 3.0)
        state = _tool_get_game_state(holder)
        assert state["active_click_rates"] == {"gold": 3.0}

    def test_no_click_rates_key_when_empty(self):
        holder = _make_holder()
        state = _tool_get_game_state(holder)
        assert "active_click_rates" not in state

    def test_new_game_clears_click_rates(self):
        holder = _make_holder()
        _tool_set_click_rate(holder, "gold", 5.0)
        _tool_new_game(holder)
        assert holder._click_rates == {}


# ── effective_rate ───────────────────────────────────────────────────


class TestEffectiveRate:
    def test_matches_rate_with_no_clicks(self):
        """With no click rates, effective_rate equals production rate."""
        holder = _make_holder()
        _tool_purchase(holder, "miner")
        state = _tool_get_game_state(holder)
        gold = state["currencies"]["gold"]
        assert gold["effective_rate"] == gold["rate"]
        assert gold["rate"] == 1.0

    def test_includes_mcp_click_income(self):
        """effective_rate includes MCP click rate * click value."""
        holder = _make_holder()
        # No production, just clicking at 5 cps. base_value=1.0 -> 5.0/sec
        _tool_set_click_rate(holder, "gold", 5.0)
        state = _tool_get_game_state(holder)
        assert state["currencies"]["gold"]["rate"] == 0.0
        assert state["currencies"]["gold"]["effective_rate"] == 5.0

    def test_production_plus_clicks(self):
        """effective_rate = production + click income."""
        holder = _make_holder()
        _tool_purchase(holder, "miner")  # 1.0/sec production
        _tool_set_click_rate(holder, "gold", 3.0)  # 3.0/sec click income
        state = _tool_get_game_state(holder)
        assert state["currencies"]["gold"]["rate"] == 1.0
        assert state["currencies"]["gold"]["effective_rate"] == 4.0

    def test_effective_rate_in_wait_response(self):
        """wait() currency summary also includes effective_rate."""
        holder = _make_holder()
        _tool_purchase(holder, "miner")
        _tool_set_click_rate(holder, "gold", 2.0)
        result = _tool_wait(holder, 1)
        assert result["currencies"]["gold"]["rate"] == 1.0
        assert result["currencies"]["gold"]["effective_rate"] == 3.0

    def test_time_to_afford_uses_effective_rate(self):
        """time_to_afford should factor in click income."""
        holder = _make_holder()
        # Spend all gold, get 1 miner (1.0/sec production)
        for _ in range(10):
            holder.runtime.try_purchase("miner")
        holder.runtime.tick(0)
        # Now 0 gold, 10 miners at 1/sec = 10/sec, cost of next miner = 10
        # Production-only time_to_afford = 10/10 = 1.0s
        result = _tool_get_available_purchases(holder)
        miner = next(p for p in result["purchases"] if p["id"] == "miner")
        assert miner["time_to_afford"] == pytest.approx(1.0)

        # Add 10 cps clicking -> effective rate 20/sec -> time = 10/20 = 0.5s
        _tool_set_click_rate(holder, "gold", 10.0)
        result = _tool_get_available_purchases(holder)
        miner = next(p for p in result["purchases"] if p["id"] == "miner")
        assert miner["time_to_afford"] == pytest.approx(0.5)

    def test_with_click_flat_effect(self):
        """Click modifiers (CLICK_FLAT) should affect effective_rate."""
        defn = GameDefinition(
            config=GameConfig(name="Click Test"),
            currencies=[CurrencyDef("gold", initial_value=100)],
            elements=[
                ElementDef(
                    id="click_boost",
                    display_name="Click Boost",
                    base_cost={"gold": 10},
                    max_count=1,
                    effects=[
                        Effect.static(EffectType.CLICK_FLAT, "gold", 4.0),
                    ],
                ),
            ],
            click_targets=[ClickTarget("gold", base_value=1.0)],
        )
        holder = _GameHolder(definition=defn, runtime=GameRuntime(defn))
        _tool_purchase(holder, "click_boost")
        # Click value = base(1.0) + flat(4.0) = 5.0 per click
        _tool_set_click_rate(holder, "gold", 2.0)
        # effective = 0 production + 2 cps * 5.0/click = 10.0/sec
        rate = _compute_effective_rate(holder, "gold")
        assert rate == pytest.approx(10.0)


# ── create_server ────────────────────────────────────────────────────


class TestCreateServer:
    def test_creates_server(self):
        from idleengine.mcp.server import create_server

        defn = _make_test_definition()
        server = create_server(defn)
        assert server is not None
