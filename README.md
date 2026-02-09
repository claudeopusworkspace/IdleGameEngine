# IdleEngine

A Python engine for building and automatically balance-testing idle/incremental games.

IdleEngine has two halves:

1. **A generic game runtime** that processes currencies, elements (generators, upgrades, unlocks), effects, and prestige mechanics through a declarative game definition.
2. **A headless simulation engine** that drives the runtime with algorithmic strategies to produce pacing reports — so you can validate your game's balance in seconds, not hours of playtesting.

Your game project imports the engine and handles its own presentation (PyGame, web, terminal — whatever you want). No UI code lives in the engine.

## Installation

```bash
pip install idleengine
```

Or install from source:

```bash
git clone <repo-url>
cd IdleGameEngine
pip install -e .
```

For visualization support (matplotlib charts):

```bash
pip install idleengine[viz]
```

**Requires Python 3.12+. Zero required dependencies.**

## Quick Start

### 1. Define your game

Create a Python file (e.g. `my_game.py`) with a `define_game()` function:

```python
from idleengine import *

def define_game() -> GameDefinition:
    return GameDefinition(
        config=GameConfig(name="My First Idle Game"),
        currencies=[
            CurrencyDef("gold", display_name="Gold", initial_value=0),
        ],
        elements=[
            ElementDef(
                id="miner",
                display_name="Miner",
                base_cost={"gold": 10},
                cost_scaling=CostScaling.exponential(1.15),
                effects=[
                    Effect.per_count("miner", EffectType.PRODUCTION_FLAT, "gold", 1.0),
                ],
            ),
        ],
        milestones=[
            MilestoneDef(
                "first_miner", "Hired first miner",
                trigger=Req.owns("miner"),
            ),
        ],
        click_targets=[ClickTarget("gold", base_value=1.0)],
    )
```

### 2. Run a simulation

```bash
python -m idleengine simulate my_game --strategy greedy_cheapest --cps 5 --terminal-time 600
```

This outputs a pacing report telling you when milestones are reached, how long players wait between purchases, and whether any stalls occur.

### 3. Use the runtime in your own game loop

```python
from idleengine import GameRuntime
from my_game import define_game

runtime = GameRuntime(define_game())

# Your game loop
while running:
    runtime.tick(delta_seconds)

    # Player clicks
    runtime.process_click("gold")

    # Player buys something
    runtime.try_purchase("miner")

    # Read state for rendering
    state = runtime.get_state()
    print(f"Gold: {state.currency_value('gold'):.0f} (+{state.currency_rate('gold'):.1f}/s)")
```

## Documentation

- **[Getting Started Guide](docs/getting-started.md)** — Full walkthrough from zero to working game
- **[Game Definition Reference](docs/game-definition.md)** — Every option for currencies, elements, effects, requirements, and more
- **[Simulation Guide](docs/simulation.md)** — Strategies, terminal conditions, pacing bounds, and the CLI
- **[API Reference](docs/api-reference.md)** — Condensed reference for all public classes and functions

## Example

See [`examples/cookie_example.py`](examples/cookie_example.py) for a complete Cookie Clicker-style game definition with prestige, synergy upgrades, milestones, and pacing bounds.

```bash
python -m idleengine simulate examples.cookie_example --strategy greedy_cheapest --cps 5 --terminal-time 3600
```

## Project Structure

```
idleengine/
    _types.py          # DynamicFloat, resolve_value(), compare()
    requirement.py     # Req factory (resource, owns, count, milestone, time, ...)
    cost_scaling.py    # CostScaling (fixed, exponential, linear, custom)
    effect.py          # EffectType enum, EffectDef, Effect convenience constructors
    currency.py        # CurrencyDef, CurrencyState
    element.py         # ElementDef, ElementState, ElementStatus
    milestone.py       # MilestoneDef
    prestige.py        # PrestigeLayerDef, PrestigeResult
    definition.py      # GameDefinition, GameConfig, ClickTarget
    state.py           # GameState
    pipeline.py        # ProductionPipeline (4-phase rate computation)
    runtime.py         # GameRuntime (tick, purchase, click, prestige)
    simulation.py      # Simulation orchestrator (tick + event-jump modes)
    strategy.py        # Strategy ABC + 5 built-in strategies
    terminal.py        # TerminalCondition ABC + 7 built-in conditions
    metrics.py         # MetricsCollector
    report.py          # SimulationReport
    pacing.py          # PacingBound
    formatting.py      # Text report output
    export.py          # CSV/JSON export
    visualization.py   # Matplotlib charts (optional)
    cli.py             # CLI entry point
```

## License

MIT
