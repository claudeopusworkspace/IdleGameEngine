"""Cookie example game from DESIGN.md Section 10."""
from __future__ import annotations

import math

from idleengine.cost_scaling import CostScaling
from idleengine.currency import CurrencyDef
from idleengine.definition import ClickTarget, GameConfig, GameDefinition
from idleengine.effect import Effect, EffectDef, EffectType
from idleengine.element import ElementDef
from idleengine.milestone import MilestoneDef
from idleengine.pacing import PacingBound
from idleengine.prestige import PrestigeLayerDef
from idleengine.requirement import Req


def define_game() -> GameDefinition:
    return GameDefinition(
        config=GameConfig(
            name="Cookie Example",
            tick_rate=10,
        ),
        currencies=[
            CurrencyDef("cookies", display_name="Cookies", initial_value=0),
            CurrencyDef(
                "prestige_chips",
                display_name="Prestige Chips",
                initial_value=0,
                persistent=True,
            ),
        ],
        elements=[
            ElementDef(
                id="cursor",
                display_name="Cursor",
                base_cost={"cookies": 15},
                cost_scaling=CostScaling.exponential(1.15),
                max_count=None,
                effects=[
                    Effect.per_count(
                        "cursor", EffectType.PRODUCTION_FLAT, "cookies", 0.1
                    ),
                ],
                requirements=[],
            ),
            ElementDef(
                id="grandma",
                display_name="Grandma",
                base_cost={"cookies": 100},
                cost_scaling=CostScaling.exponential(1.15),
                max_count=None,
                effects=[
                    Effect.per_count(
                        "grandma", EffectType.PRODUCTION_FLAT, "cookies", 1.0
                    ),
                ],
                requirements=[Req.count("cursor", ">=", 1)],
            ),
            ElementDef(
                id="farm",
                display_name="Farm",
                base_cost={"cookies": 1100},
                cost_scaling=CostScaling.exponential(1.15),
                max_count=None,
                effects=[
                    Effect.per_count(
                        "farm", EffectType.PRODUCTION_FLAT, "cookies", 8.0
                    ),
                ],
                requirements=[Req.count("grandma", ">=", 1)],
            ),
            ElementDef(
                id="double_cookies",
                display_name="Cookie Doubler",
                base_cost={"cookies": 500},
                cost_scaling=CostScaling.fixed(),
                max_count=1,
                effects=[
                    Effect.static(EffectType.PRODUCTION_MULT, "cookies", 2.0),
                ],
                requirements=[Req.total_earned("cookies", ">=", 1000)],
                tags={"upgrade"},
            ),
            ElementDef(
                id="grandma_synergy",
                display_name="Grandma's Secret Recipe",
                base_cost={"cookies": 5000},
                cost_scaling=CostScaling.fixed(),
                max_count=1,
                effects=[
                    EffectDef(
                        type=EffectType.PRODUCTION_FLAT,
                        target="cookies",
                        value=lambda s: (
                            s.element_count("grandma")
                            * s.element_count("farm")
                            * 0.05
                        ),
                    ),
                ],
                requirements=[
                    Req.count("grandma", ">=", 5),
                    Req.count("farm", ">=", 3),
                ],
                tags={"upgrade", "synergy"},
            ),
        ],
        milestones=[
            MilestoneDef(
                "first_purchase",
                "First generator bought",
                trigger=Req.custom(
                    lambda s: (
                        s.element_count("cursor")
                        + s.element_count("grandma")
                        + s.element_count("farm")
                        >= 1
                    )
                ),
            ),
            MilestoneDef(
                "hundred_cps",
                "100 cookies/sec",
                trigger=Req.custom(
                    lambda s: s.currency_rate("cookies") >= 100
                ),
            ),
            MilestoneDef(
                "million_cookies",
                "1M cookies earned",
                trigger=Req.total_earned("cookies", ">=", 1_000_000),
            ),
        ],
        prestige_layers=[
            PrestigeLayerDef(
                id="prestige",
                prestige_currency="prestige_chips",
                reward_formula=lambda s: math.floor(
                    s.total_earned("cookies") / 1_000_000
                )
                ** 0.5,
                currencies_reset=["cookies"],
                elements_reset=[
                    "cursor",
                    "grandma",
                    "farm",
                    "double_cookies",
                    "grandma_synergy",
                ],
                requirements=[Req.total_earned("cookies", ">=", 1_000_000)],
                minimum_reward=1.0,
            ),
        ],
        pacing_bounds=[
            PacingBound.milestone_between("first_purchase", 3, 20),
            PacingBound.milestone_between("hundred_cps", 120, 600),
            PacingBound.milestone_between("million_cookies", 1800, 5400),
            PacingBound.max_gap_between_purchases(90, after_time=30),
            PacingBound.no_stalls(),
        ],
        click_targets=[
            ClickTarget("cookies", base_value=1.0),
        ],
    )
