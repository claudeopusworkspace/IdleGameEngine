# Getting Started

This guide walks you through building your first idle game with IdleEngine.

## Install

```bash
pip install idleengine
```

Or from a local clone:

```bash
pip install -e .
```

## Core Concept

An IdleEngine game is defined entirely in Python as a `GameDefinition` — a declarative blueprint that lists your currencies, purchasable elements, effects, milestones, and pacing expectations. You hand this definition to a `GameRuntime`, which handles all game logic. You never write game logic yourself; you configure it.

The same definition is used for both interactive play and headless simulation. There is no "simulation version" that can drift from reality.

## Step 1: Create a Game Module

Create a file called `my_game.py`. The only requirement is that it exports a `define_game()` function returning a `GameDefinition`:

```python
from idleengine import *

def define_game() -> GameDefinition:
    return GameDefinition(
        config=GameConfig(name="Gold Rush"),
        currencies=[...],
        elements=[...],
        milestones=[...],
        click_targets=[...],
    )
```

## Step 2: Define Currencies

Currencies are any numeric quantity that can be earned, spent, and tracked. Gold, mana, prestige points, population — if it's a number that goes up and down, it's a currency.

```python
currencies=[
    CurrencyDef("gold", display_name="Gold", initial_value=0),
    CurrencyDef("gems", display_name="Gems", initial_value=0, cap=100),
    CurrencyDef(
        "prestige_pts",
        display_name="Prestige Points",
        initial_value=0,
        persistent=True,   # survives prestige resets
    ),
]
```

Key fields:
- `initial_value` — starting amount (default 0)
- `cap` — maximum value, or `None` for uncapped. Can be a callable: `cap=lambda s: 100 + s.element_count("warehouse") * 50`
- `persistent` — if `True`, this currency is not reset during prestige

## Step 3: Define Elements

Elements are anything the player can acquire: generators, upgrades, one-time unlocks. There are no rigid subtypes — an element's behavior comes from its configuration.

### A basic generator

```python
ElementDef(
    id="miner",
    display_name="Gold Miner",
    base_cost={"gold": 50},
    cost_scaling=CostScaling.exponential(1.15),  # each one costs 15% more
    effects=[
        Effect.per_count("miner", EffectType.PRODUCTION_FLAT, "gold", 2.0),
        # Each miner produces 2 gold/sec
    ],
)
```

### A one-time upgrade

```python
ElementDef(
    id="double_gold",
    display_name="Gold Rush",
    base_cost={"gold": 1000},
    cost_scaling=CostScaling.fixed(),
    max_count=1,    # can only buy once
    effects=[
        Effect.static(EffectType.PRODUCTION_MULT, "gold", 2.0),
        # Doubles all gold production
    ],
    requirements=[Req.total_earned("gold", ">=", 5000)],
    tags={"upgrade"},
)
```

### A gated element

```python
ElementDef(
    id="wizard",
    display_name="Wizard",
    base_cost={"gold": 500, "gems": 10},
    cost_scaling=CostScaling.exponential(1.20),
    effects=[
        Effect.per_count("wizard", EffectType.PRODUCTION_FLAT, "gems", 0.5),
    ],
    requirements=[
        Req.count("miner", ">=", 5),       # need 5 miners first
        Req.milestone("unlocked_magic"),     # need a milestone too
    ],
)
```

## Step 4: Define Milestones

Milestones are named one-time events that fire when a condition is met. They serve as pacing markers and can trigger side effects.

```python
milestones=[
    MilestoneDef(
        "first_purchase", "Made first purchase",
        trigger=Req.custom(lambda s: s.element_count("miner") >= 1),
    ),
    MilestoneDef(
        "hundred_gps", "Reached 100 gold/sec",
        trigger=Req.custom(lambda s: s.currency_rate("gold") >= 100),
    ),
    MilestoneDef(
        "millionaire", "Earned 1M gold total",
        trigger=Req.total_earned("gold", ">=", 1_000_000),
    ),
]
```

## Step 5: Define Click Targets

If your game has clicking, declare which currencies can be clicked and their base value:

```python
click_targets=[
    ClickTarget("gold", base_value=1.0),
]
```

Click values are modified by `CLICK_FLAT` and `CLICK_MULT` effects from owned elements.

## Step 6: Run a Simulation

From the command line:

```bash
python -m idleengine simulate my_game --strategy greedy_cheapest --cps 5 --terminal-time 3600
```

This simulates a player who clicks 5 times/sec and always buys the cheapest available element, for up to 1 hour of game time.

Or from Python:

```python
from idleengine import Simulation, GreedyCheapest, ClickProfile, Terminal, format_text_report
from my_game import define_game

sim = Simulation(
    definition=define_game(),
    strategy=GreedyCheapest(click_profile=ClickProfile(targets={"gold": 5.0})),
    terminal=Terminal.time(3600),
)
report = sim.run()
print(format_text_report(report))
```

## Step 7: Add Pacing Bounds

Pacing bounds let you declare expectations about game timing. The simulation checks these and reports pass/fail.

```python
pacing_bounds=[
    PacingBound.milestone_between("first_purchase", min_sec=3, max_sec=20),
    PacingBound.milestone_between("hundred_gps", min_sec=120, max_sec=600),
    PacingBound.max_gap_between_purchases(max_sec=90, after_time=30),
    PacingBound.no_stalls(),
    PacingBound.dead_time_ratio(max_ratio=0.30),
]
```

## Step 8: Integrate with Your Game

The runtime is the same object used by the simulation. Use it in your own game loop:

```python
runtime = GameRuntime(define_game())

# Main loop
while running:
    runtime.tick(delta_seconds)
    state = runtime.get_state()

    # Render: read state.currency_value(), state.currency_rate(), etc.
    # Input: call runtime.try_purchase("miner"), runtime.process_click("gold")
    # Query: runtime.get_affordable_purchases() for UI button states
```

See [`examples/cookie_example.py`](../examples/cookie_example.py) for a complete working game.

## Next Steps

- [Game Definition Reference](game-definition.md) — all available options
- [Simulation Guide](simulation.md) — strategies, terminal conditions, export
- [API Reference](api-reference.md) — condensed class/function reference
