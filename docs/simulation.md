# Simulation Guide

IdleEngine's simulation replaces human input with algorithmic strategies, playing through your game at arbitrary speed and producing quantitative pacing reports.

## Running a Simulation

### From the CLI

```bash
python -m idleengine simulate <game_module> [options]
```

`<game_module>` is a Python import path to a module with a `define_game()` function. For a file at `my_game.py` in the current directory, use `my_game`. For the bundled example, use `examples.cookie_example`.

**Options:**

| Flag | Default | Description |
|---|---|---|
| `--strategy` | `greedy_cheapest` | Strategy: `greedy_cheapest`, `greedy_roi`, `save_for_best` |
| `--cps` | `0` | Simulated clicks per second |
| `--click-target` | auto | Currency to click (defaults to first click target) |
| `--terminal-time` | `3600` | Max simulation time in seconds |
| `--tick-resolution` | `1.0` | Seconds per simulation tick |
| `--mode` | `tick` | `tick` or `event_jump` |
| `--seed` | random | RNG seed for reproducibility |
| `--export-csv` | — | Path prefix for CSV export |
| `--export-json` | — | Path for JSON export |
| `--plot` | — | Path for matplotlib chart (PNG) |
| `--monte-carlo` | — | Run N simulations, report aggregate stats |

**Examples:**

```bash
# Basic run with clicking
python -m idleengine simulate my_game --cps 5 --terminal-time 7200

# Event-jump mode (fast, for games with static rates)
python -m idleengine simulate my_game --cps 5 --mode event_jump --terminal-time 7200

# Export data
python -m idleengine simulate my_game --cps 5 --export-json report.json --export-csv data

# Monte Carlo (10 runs with randomized estimated_time requirements)
python -m idleengine simulate my_game --cps 5 --monte-carlo 10 --seed 42

# Reproducible run
python -m idleengine simulate my_game --cps 5 --seed 12345
```

### From Python

```python
from idleengine import (
    Simulation, GreedyCheapest, ClickProfile, Terminal,
    format_text_report,
)
from my_game import define_game

defn = define_game()

sim = Simulation(
    definition=defn,
    strategy=GreedyCheapest(
        click_profile=ClickProfile(targets={"gold": 5.0}),
    ),
    terminal=Terminal.time(3600),
    tick_resolution=1.0,
    seed=42,
    mode="tick",       # or "event_jump"
)

report = sim.run()
print(format_text_report(report, defn.pacing_bounds))
```

## Simulation Modes

### Tick Mode (default)

Steps through time at a fixed resolution (default 1 second per tick). Each tick:

1. Advance game time by `tick_resolution` seconds
2. Process clicks from the strategy
3. Evaluate and execute purchases
4. Evaluate prestige
5. Check milestones
6. Record metrics

Most general mode. Works for any game.

### Event-Jump Mode

Skips forward in time to the next affordable purchase instead of ticking every second. Much faster for games where production rates are stable between purchases.

When nothing is affordable, it computes time-to-afford for every available element (including income from clicks), jumps to the soonest one, and applies accumulated production and click earnings.

If no element will ever become affordable (zero income), it detects a **stall** and stops.

Use event-jump mode when:
- Your game has simple, continuous production between purchases
- You want faster simulation of long runs
- You want automatic stall detection

## Strategies

Strategies control what the simulated player buys, clicks, and when they prestige.

### GreedyCheapest

The baseline. Sorts affordable elements by total cost (ascending) and buys the cheapest first. Continues buying until nothing is affordable.

```python
GreedyCheapest(
    click_profile=ClickProfile(targets={"gold": 5.0}),
    prestige_mode="never",      # or "first_opportunity"
    cost_weights={"gems": 10},  # optional: weight gem costs higher
)
```

### GreedyROI

Buys the element that gives the best immediate rate-of-return (delta_rate / cost). Approximates a savvy player.

```python
sim = Simulation(definition=defn, strategy=GreedyROI(), terminal=terminal)
# Link runtime after creation:
strategy = GreedyROI(click_profile=ClickProfile(targets={"gold": 5.0}))
sim = Simulation(definition=defn, strategy=strategy, terminal=terminal)
strategy.runtime = sim.runtime  # GreedyROI needs runtime access
```

### SaveForBest

Computes ROI for all available elements (not just affordable), then saves for the single best one. Models a patient, planning player.

```python
strategy = SaveForBest(click_profile=ClickProfile(targets={"gold": 3.0}))
sim = Simulation(definition=defn, strategy=strategy, terminal=terminal)
strategy.runtime = sim.runtime
```

### PriorityList

Follows a designer-specified purchase order. Useful for testing a specific intended path through the game.

```python
PriorityList(
    priorities=[
        ("miner", 5),       # buy 5 miners first
        ("upgrade_1", 1),   # then the upgrade
        ("miner", 15),      # then more miners
    ],
    fallback=GreedyCheapest(),  # after priorities are met
    click_profile=ClickProfile(targets={"gold": 5.0}),
)
```

### CustomStrategy

For testing specific hypotheses:

```python
CustomStrategy(
    decide_fn=lambda state, affordable: [affordable[0].id] if affordable else [],
    clicks_fn=lambda state, duration, waiting: {"gold": int(3 * duration)},
    prestige_fn=lambda state, layer_id: state.total_earned("gold") > 1e9,
    name="MyCustom",
)
```

## Click Profiles

`ClickProfile` configures how the simulated player clicks:

```python
ClickProfile(
    targets={"gold": 5.0, "mana": 2.0},  # 5 CPS on gold, 2 on mana
    active_until=Req.custom(lambda s: s.currency_rate("gold") > 50),
        # stop clicking gold once passive income exceeds 50/sec
    active_during_wait=True,
        # keep clicking while waiting for a purchase (important for event-jump mode)
)
```

## Terminal Conditions

Terminal conditions define when the simulation stops.

```python
Terminal.time(7200)                          # after 2 hours
Terminal.milestone("endgame")                # when milestone reached
Terminal.currency("gold", ">=", 1e15)        # when gold hits threshold
Terminal.all_purchased(element_ids=["a","b"])  # when specific elements bought
Terminal.stall(max_idle_seconds=600)          # 10min with no purchase
Terminal.any(t1, t2, t3)                     # first met stops
Terminal.all(t1, t2)                         # all must be met
```

Combine for practical use:

```python
terminal = Terminal.any(
    Terminal.milestone("beat_game"),
    Terminal.time(14400),       # safety cap: 4 hours
    Terminal.stall(600),        # give up after 10min idle
)
```

## Interpreting Strategy Results: Human Speed Multiplier

Built-in strategies do **not** model human intelligence. Real players complete games significantly faster than `GreedyCheapest` because they:

1. Recognize high-ROI purchases that GreedyCheapest misses (it always buys the cheapest available)
2. Plan ahead and save for expensive-but-powerful items
3. Develop intuition for which multipliers compound best

Across multiple prototype games, human players consistently complete **2-3x faster** than GreedyCheapest simulations. Treat GreedyCheapest as a conservative lower bound on player skill.

**Practical guidance for pacing bounds:**

- If you want at least 8 hours of human gameplay, set your `PacingBound` minimum to ~16-20 hours for GreedyCheapest
- If you want the game completable in 4 hours by humans, set the maximum to ~8-12 hours for GreedyCheapest

**Test with multiple strategies** to bracket human performance:

```python
# Lower bound (worst player): GreedyCheapest
sim_cheap = Simulation(definition=defn, strategy=GreedyCheapest(...), terminal=terminal)

# Better approximation: GreedyROI
strategy_roi = GreedyROI(click_profile=ClickProfile(targets={"gold": 5.0}))
sim_roi = Simulation(definition=defn, strategy=strategy_roi, terminal=terminal)
strategy_roi.runtime = sim_roi.runtime

# Human performance is likely somewhere between GreedyROI and 2x faster than GreedyROI
```

| Strategy | Relative Speed | Models |
|---|---|---|
| `GreedyCheapest` | 1x (baseline) | Least skilled player |
| `GreedyROI` | ~1.5-2x faster | Moderately skilled player |
| `SaveForBest` | ~2-3x faster | Patient, planning player |
| Real human | ~2-3x faster than GreedyCheapest | Varies widely |

## Pacing Bounds

Pacing bounds are pass/fail checks declared in your game definition. The simulation evaluates them and reports results.

```python
pacing_bounds=[
    # Milestone timing windows
    PacingBound.milestone_between("first_purchase", min_sec=3, max_sec=20),
    PacingBound.milestone_between("prestige_ready", min_sec=600, max_sec=1800),

    # No more than 90sec between purchases (after the first 30sec)
    PacingBound.max_gap_between_purchases(max_sec=90, after_time=30),

    # No deadlocks
    PacingBound.no_stalls(),

    # Less than 30% of time spent with nothing to do
    PacingBound.dead_time_ratio(max_ratio=0.30),

    # Arbitrary check
    PacingBound.custom(
        lambda report: report.total_time < 14400,
        "Game completable in 4 hours",
    ),
]
```

Each bound has a severity: `"error"` (default) or `"warning"`.

## Simulation Report

`Simulation.run()` returns a `SimulationReport` with:

| Field | Type | Description |
|---|---|---|
| `total_time` | `float` | Total simulated time |
| `outcome` | `str` | How the simulation ended |
| `milestone_times` | `dict[str, float]` | Milestone ID -> time reached |
| `purchases` | `list[PurchaseEvent]` | Every purchase with time, cost, state |
| `purchase_gaps` | `list[float]` | Time between consecutive purchases |
| `max_purchase_gap` | `float` | Longest gap |
| `mean_purchase_gap` | `float` | Average gap |
| `dead_time_ratio` | `float` | Fraction of time spent waiting |
| `purchases_per_minute` | `float` | Purchase cadence |
| `stalls` | `list[StallEvent]` | Detected stalls |
| `currency_snapshots` | `list[CurrencySnapshot]` | Time-series data |

**Query methods:**

```python
report.milestone_time("first_purchase")      # -> float | None
report.currency_series("gold")               # -> [(time, value), ...]
report.rate_series("gold")                   # -> [(time, rate), ...]
```

## Export

### CSV

```python
from idleengine.export import export_csv
export_csv(report, "output/data")
# Creates: output/data_currencies.csv, output/data_purchases.csv, output/data_milestones.csv
```

### JSON

```python
from idleengine.export import export_json
export_json(report, "output/report.json")
```

### Matplotlib Charts

Requires `pip install idleengine[viz]`.

```python
from idleengine.visualization import plot_simulation
plot_simulation(report, "output/chart.png")   # save to file
plot_simulation(report)                        # show interactive window
```

Generates a 4-panel chart: currency values (log scale), production rates, purchase timeline, and purchase gap histogram.
