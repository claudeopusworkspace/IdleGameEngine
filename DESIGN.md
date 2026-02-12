# IdleEngine — Technical Design Document

## Generic Idle Game Engine & Automated Balance Simulation Framework

---

## 1. Introduction & Motivation

Idle/incremental games share a remarkably consistent structural backbone despite surface-level variety: the player accumulates **currencies**, spends them on **elements** (generators, upgrades, unlocks), and those elements modify the rates and rules of accumulation. The genre's design challenge is almost entirely one of **pacing** — ensuring the player always feels meaningful progression without either stalling or trivializing content.

This document proposes **IdleEngine**, a framework with two equally important halves:

1. **A generic runtime** capable of expressing any idle game's economy, progression, and mechanics through a declarative game definition augmented with callable hooks.
2. **A headless simulation engine** that consumes the same game definition to automatically play through the game under configurable strategies, producing quantitative pacing reports and pass/fail balance checks.

The key architectural insight is that both the real game and the simulation share the same `GameRuntime`. The simulation simply replaces human input with algorithmic decision-making and rendering with metric collection.

### Goals

- Define once, play and simulate with the same source of truth
- Catch hard pacing problems before any human touches the game
- Support rapid prototyping: swap out a game definition, immediately get a new pacing report
- Generic enough to express Cookie Clicker, Antimatter Dimensions, Kittens Game, Melvor Idle, or anything in between
- PyGame presentation layer for lightweight interactive prototyping

### Non-Goals (For Now)

- Multiplayer or networked play
- Mobile deployment (PyGame is the target)
- Visual/spatial simulation (tile placement, pathfinding, etc.)
- AI that discovers optimal strategies (we test *specific* strategies, not solve the game)

---

## 2. Design Principles

| Principle | Implication |
|---|---|
| **Definition ≠ State ≠ Presentation** | A `GameDefinition` is a static blueprint. `GameState` is a mutable snapshot. `Presenter` reads state and draws. None reference each other circularly. |
| **Callables as Escape Hatches** | Every value that *could* be dynamic accepts either a literal or a `Callable[[GameState], T]`. This covers synergies, conditional effects, and scaling without needing a DSL. |
| **Simulation is First-Class** | The simulation isn't a test bolted on after the fact. The runtime is designed from the start to operate headlessly at arbitrary speed. |
| **Composition over Taxonomy** | There are no rigid "Generator" vs "Upgrade" vs "Prestige" classes. An `Element` is configured with properties that make it behave as any of those. |
| **Explicit Pacing Contract** | Game designers declare expected pacing bounds. The simulation reports whether those bounds are satisfied. Balance is not a vibe — it's a test suite. |

---

## 3. High-Level Architecture

```
┌──────────────────────────────────────────────────────┐
│                   GameDefinition                     │
│  Currencies · Elements · Effects · Requirements      │
│  Milestones · Prestige Layers · Config               │
└──────────────────────┬───────────────────────────────┘
                       │ consumed by
                       ▼
┌──────────────────────────────────────────────────────┐
│                    GameRuntime                        │
│  Owns GameState · Computes production pipeline       │
│  Processes purchases · Evaluates requirements        │
│  Fires milestones · Handles prestige resets          │
└─────────┬────────────────────────────┬───────────────┘
          │                            │
          ▼                            ▼
┌──────────────────┐     ┌─────────────────────────────┐
│  PyGame Presenter│     │    Simulation Engine         │
│  Reads state     │     │    Drives runtime headlessly │
│  Captures input  │     │    Applies strategy          │
│  Renders UI      │     │    Collects metrics          │
└──────────────────┘     │    Checks pacing bounds      │
                         │    Produces reports           │
                         └─────────────────────────────┘
```

The critical boundary: **GameRuntime exposes a pure API with no knowledge of who is calling it.** The presenter calls `runtime.try_purchase("farm")` when the player clicks a button. The simulation calls the same method when its strategy decides to buy. The runtime doesn't know or care.

---

## 4. Core Data Model

### 4.1 Currency

A **Currency** is any numeric quantity that can be earned, spent, and tracked.

```
CurrencyDef:
    id: str                          # "gold", "prestige_points", "research"
    display_name: str
    initial_value: float             # starting amount (usually 0)
    cap: float | Callable | None     # max value, None = uncapped
    persistent: bool                 # survives prestige resets? default False
    hidden_until: Requirement | None # not shown to player until condition met
```

**Design note:** Things that feel like "stats" (DPS, population, territory) are still currencies. If the game tracks a number that can go up and down, it's a currency. The production pipeline handles how it changes over time.

The runtime tracks, per currency:
- `current`: present value
- `total_earned`: lifetime total (useful for unlock conditions — "earn 1M gold total" is different from "have 1M gold right now")
- `current_rate`: computed production per second (cached, recalculated on state changes)

### 4.2 Element

An **Element** is anything the player can acquire. Generators, upgrades, one-time unlocks, prestige actions — all are elements with different configurations.

```
ElementDef:
    id: str                          # "farm", "gold_multiplier_1", "prestige"
    display_name: str
    description: str | Callable      # can be dynamic ("Currently: +{value}/sec")
    
    # --- Cost ---
    base_cost: dict[str, float]      # {"gold": 100, "gems": 5}
    cost_scaling: CostScaling        # how cost changes with count
    
    # --- Limits ---
    max_count: int | None            # None = unlimited, 1 = one-time upgrade
    
    # --- Effects ---
    effects: list[EffectDef]         # what owning this does
    
    # --- Requirements ---
    requirements: list[Requirement]  # must ALL be met to make visible/available
    purchase_requirements: list[Requirement]  # additional reqs beyond affordability
    
    # --- Special Behavior ---
    on_purchase: Callable | None     # callback for side effects (prestige, etc.)
    
    # --- Metadata ---
    tags: set[str]                   # for filtering, UI grouping, strategy hints
    category: str                    # UI tab/section
```

**Cost Scaling** is defined as a strategy object with common presets:

```
CostScaling:
    compute(base_cost: dict, current_count: int) -> dict[str, float]
    
    # Presets:
    CostScaling.fixed()                              # always base_cost
    CostScaling.exponential(growth_rate=1.15)        # base * growth^count
    CostScaling.linear(increment_pct=0.10)           # base * (1 + pct * count)
    CostScaling.custom(fn: Callable)                 # anything
```

**Element state** tracked at runtime:
- `count`: how many owned (0 to max_count)
- `available`: are all requirements met?
- `affordable`: can the player pay the current cost?

### 4.3 Effect

An **Effect** describes a modification to the game state that is active while an element is owned (and optionally, while a condition is true). Effects are the core building block of game mechanics.

```
EffectDef:
    type: EffectType
    target: str                      # currency id, element id, or special target
    value: float | Callable          # static or dynamic (receives GameState)
    condition: Requirement | None    # only active when this is true
    phase: EffectPhase               # when in the pipeline this applies
```

**EffectType Enumeration:**

| Type | What It Does | Phase |
|---|---|---|
| `PRODUCTION_FLAT` | Adds flat amount to currency production rate | BASE |
| `PRODUCTION_ADD_PCT` | Adds additive percentage to currency production | BONUS_ADD |
| `PRODUCTION_MULT` | Multiplies currency production | BONUS_MULT |
| `GLOBAL_MULT` | Multiplies ALL currency production | GLOBAL |
| `CLICK_FLAT` | Adds flat amount to click value for a currency | CLICK |
| `CLICK_MULT` | Multiplies click value for a currency | CLICK |
| `COST_MULT` | Multiplies cost of target element(s) | COST |
| `CAP_FLAT` | Adds to currency cap | CAP |
| `CAP_MULT` | Multiplies currency cap | CAP |
| `AUTO_CLICK` | Generates automatic clicks/sec on a target | AUTO |
| `GRANT` | One-time resource grant on purchase (not ongoing) | IMMEDIATE |
| `UNLOCK` | Makes target element available (bypasses its requirements) | IMMEDIATE |
| `CUSTOM` | Arbitrary callback, registered with the runtime | CUSTOM |

**The Production Pipeline** for a given currency each tick:

```
1. flat_sum = Σ (all active PRODUCTION_FLAT effects targeting this currency)
2. add_pct  = Σ (all active PRODUCTION_ADD_PCT effects targeting this currency)
3. mult     = Π (all active PRODUCTION_MULT effects targeting this currency)
4. global   = Π (all active GLOBAL_MULT effects)

rate = flat_sum × (1 + add_pct) × mult × global
```

**Convenience constructors** for common patterns:

```python
# "+2 food/sec per farm owned"
Effect.per_count(element="farm", type=PRODUCTION_FLAT, target="food", per_unit=2.0)
# Internally: value = lambda state: state.element_count("farm") * 2.0

# "Double gold production"  
Effect.static(type=PRODUCTION_MULT, target="gold", value=2.0)

# "+1% gold/sec for each farm owned"
Effect.synergy(source="farm", type=PRODUCTION_ADD_PCT, target="gold", per_unit=0.01)
```

### 4.4 Requirement

A **Requirement** is a boolean condition evaluated against game state. Requirements are used for element visibility, purchase gating, milestone triggers, and effect conditions.

```
Requirement (interface):
    evaluate(state: GameState) -> bool
```

**Built-in requirement types:**

| Type | Constructor | Evaluates True When |
|---|---|---|
| Resource threshold | `Req.resource("gold", ">= ", 1000)` | Current gold ≥ 1000 |
| Lifetime earned | `Req.total_earned("gold", ">=", 1e6)` | Total gold earned ≥ 1M |
| Element owned | `Req.owns("farm")` | Player owns ≥1 farm |
| Element count | `Req.count("farm", ">=", 10)` | Player owns ≥10 farms |
| Milestone reached | `Req.milestone("unlocked_lab")` | Milestone has fired |
| Time elapsed | `Req.time(">=", 300)` | Game time ≥ 5 minutes |
| Composite AND | `Req.all(req1, req2, req3)` | All sub-requirements true |
| Composite OR | `Req.any(req1, req2)` | Any sub-requirement true |
| Custom lambda | `Req.custom(lambda s: ...)` | Lambda returns True |
| **Estimated time** | `Req.estimated_time(120, variance=30)` | *Simulation only:* draws from distribution |

The **Estimated Time** requirement is a critical design feature for simulation. Some game events can't be deterministically simulated — boss kills, puzzle completion, player exploration. Rather than ignoring them, the designer specifies an expected duration. During simulation, the requirement becomes true after sampling from a distribution (normal with given mean/variance, or uniform over a range). During real gameplay, it's replaced with actual logic or a flag set by game code.

```python
# "Player discovers the hidden cave" — can't simulate, estimate 2-5 minutes of play
Req.estimated_time(mean=210, variance=90, description="Discover hidden cave")
```

### 4.5 Milestone

A **Milestone** is a named event that fires once when its condition is met. Milestones serve as pacing markers and unlock triggers.

```
MilestoneDef:
    id: str
    description: str
    trigger: Requirement               # when does this fire?
    on_trigger: Callable | None        # optional side effect
    pacing_note: str | None            # design intent ("player should reach this around 10min")
```

Milestones are tracked by the simulation as timestamps, forming the primary data for pacing analysis.

### 4.6 Prestige Layer

A **Prestige Layer** defines a reset mechanic. Many idle games have multiple layers (prestige, transcendence, etc.).

```
PrestigeLayerDef:
    id: str                             # "prestige", "transcend"
    prestige_currency: str              # which currency is gained
    
    # How much prestige currency is earned (function of current state)
    reward_formula: Callable[[GameState], float]
    
    # What happens on reset
    currencies_reset: list[str] | "all_non_persistent"
    elements_reset: list[str] | "all_non_persistent"  
    
    # Requirements to trigger
    requirements: list[Requirement]
    
    # Optional minimum reward threshold (don't let player prestige for 0 gain)
    minimum_reward: float
```

Elements and currencies have a `persistent` flag and optionally a `prestige_layer` tag indicating which reset they survive.

---

## 5. Runtime Systems

### 5.1 GameState

The full mutable state of a game in progress:

```
GameState:
    time_elapsed: float                          # total game time in seconds
    currencies: dict[str, CurrencyState]         # current, total_earned, current_rate
    elements: dict[str, ElementState]            # count, available, affordable
    milestones_reached: dict[str, float]         # milestone_id -> time_reached
    prestige_counts: dict[str, int]              # how many times each layer reset
    run_number: int                              # current prestige run
    
    # Convenience accessors
    def currency_value(self, id) -> float
    def currency_rate(self, id) -> float
    def element_count(self, id) -> int
    def has_milestone(self, id) -> bool
    def total_earned(self, id) -> float
```

### 5.2 GameRuntime

The runtime is the authoritative game logic processor.

```
GameRuntime:
    def __init__(self, definition: GameDefinition)
    
    # --- Core loop ---
    def tick(self, delta_seconds: float)
        # 1. Recompute production rates (evaluate all active effects)
        # 2. Apply production: currency += rate * delta for each currency
        # 3. Apply auto-click effects
        # 4. Re-evaluate element availability and affordability
        # 5. Check milestone triggers
    
    # --- Player actions ---
    def try_purchase(self, element_id: str) -> bool
        # Check available + affordable
        # Deduct costs
        # Increment count
        # Apply IMMEDIATE effects (GRANT, UNLOCK)
        # Fire on_purchase callback
        # Mark state dirty (triggers rate recomputation)
    
    def process_click(self, target_currency: str) -> float
        # Compute click value through click pipeline
        # Add to currency
        # Return amount added (for UI feedback)
    
    def trigger_prestige(self, layer_id: str) -> PrestigeResult
        # Compute reward
        # Apply reset rules
        # Grant prestige currency
        # Increment run counter
    
    # --- Queries ---
    def get_state(self) -> GameState  # read-only snapshot
    def get_available_purchases(self) -> list[ElementStatus]
    def get_affordable_purchases(self) -> list[ElementStatus]
    def compute_current_cost(self, element_id: str) -> dict[str, float]
    def compute_time_to_afford(self, element_id: str) -> float | None
        # Returns seconds until affordable at current rates
        # None if rate is zero or negative for a required currency
```

### 5.3 Production Rate Computation

Performed once per tick (or on state change). Iterates all owned elements, collects active effects, and runs the pipeline described in §4.3.

For each currency `c`:
```
active_effects = []
for element in all_elements:
    if element.count > 0:
        for effect in element.effects:
            if effect.targets(c) and effect.condition_met(state):
                active_effects.append(effect.evaluate(state))

# Also include system-level effects (global modifiers, prestige bonuses)
for sys_effect in system_effects:
    if sys_effect.targets(c) and sys_effect.condition_met(state):
        active_effects.append(sys_effect.evaluate(state))

rate = pipeline(active_effects)  # BASE → BONUS_ADD → BONUS_MULT → GLOBAL
state.currencies[c].current_rate = rate
```

---

## 6. Simulation Engine

### 6.1 Overview

The simulation engine wraps a `GameRuntime` and drives it without human input. Its purpose is to play through the game under a given **strategy** and collect **pacing metrics**.

```
Simulation:
    def __init__(self, 
                 definition: GameDefinition, 
                 strategy: Strategy,
                 terminal: TerminalCondition,
                 tick_resolution: float = 1.0,  # seconds per tick
                 seed: int | None = None)        # for estimated_time randomness
    
    def run(self) -> SimulationReport
```

### 6.2 Simulation Loop

Two modes of operation:

**Tick Mode** (default, most general):

```
while not terminal.is_met(state):
    # 1. Advance time
    runtime.tick(tick_resolution)
    
    # 2. Process clicks
    clicks = strategy.get_clicks(state, tick_resolution)
    for target, count in clicks.items():
        for _ in range(count):
            runtime.process_click(target)
    
    # 3. Evaluate purchases
    available = runtime.get_affordable_purchases()
    to_buy = strategy.decide_purchases(state, available)
    for element_id in to_buy:
        runtime.try_purchase(element_id)
    
    # 4. Evaluate prestige
    for layer in definition.prestige_layers:
        if strategy.should_prestige(state, layer.id):
            runtime.trigger_prestige(layer.id)
    
    # 5. Record metrics
    metrics.record_tick(state)
```

**Event-Jump Mode** (faster, for games with static rates between purchases):

```
while not terminal.is_met(state):
    affordable = runtime.get_affordable_purchases()
    
    if affordable:
        to_buy = strategy.decide_purchases(state, affordable)
        for element_id in to_buy:
            runtime.try_purchase(element_id)
        metrics.record_purchase(state, element_id)
    else:
        # Find next affordable element and jump to that time
        candidates = runtime.get_available_purchases()  # available but not affordable
        times = {e.id: runtime.compute_time_to_afford(e.id) for e in candidates}
        times = {k: v for k, v in times.items() if v is not None}
        
        if not times:
            # Nothing will ever become affordable — stall detected!
            metrics.record_stall(state)
            break
        
        next_id = min(times, key=times.get)
        jump_duration = times[next_id]
        
        # Apply accumulated clicks during the wait
        clicks_during_wait = strategy.get_clicks_for_duration(state, jump_duration)
        
        runtime.tick(jump_duration)
        # Apply click earnings
        for target, total in clicks_during_wait.items():
            state.currencies[target].current += total
        
        metrics.record_wait(state, jump_duration)
```

Event-jump mode can **detect stalls** (no purchase will ever become affordable) which is itself a critical balance finding. It can also detect when a stall is broken only by clicking, which indicates a pacing bottleneck.

### 6.3 Strategy Interface

```
Strategy (interface):
    def decide_purchases(self, 
                         state: GameState, 
                         affordable: list[ElementStatus]) -> list[str]:
        """Given current state and affordable elements, return ordered list of element IDs to buy."""
    
    def get_clicks(self, 
                   state: GameState, 
                   duration: float) -> dict[str, int]:
        """Return number of clicks per target during this tick duration."""
    
    def should_prestige(self, 
                        state: GameState, 
                        layer_id: str) -> bool:
        """Should we trigger this prestige layer right now?"""
```

### 6.4 Built-In Strategies

**GreedyCheapest** — The baseline "buy everything at first opportunity" strategy from the original concept.
- Purchases: Sort affordable by total cost (sum of all currency costs, optionally weighted), buy cheapest first. Continue buying until nothing is affordable.
- Clicks: Configurable constant CPS on the primary currency. Clicks stop when production rate exceeds a configurable threshold (models player going idle once generators take over).
- Prestige: Never (single-run analysis) or at first opportunity.

**GreedyROI** — Buy what gives the best immediate return on investment.
- For each affordable element, compute `Δrate / cost` where Δrate is the increase in total production the element would provide. Buy the highest ratio first.
- This approximates a somewhat savvy player and should yield better pacing than GreedyCheapest.

**SaveForBest** — Always save for the single most impactful available element.
- Compute ROI for all *available* elements (not just affordable). Save for the best one. Only buy it when affordable.
- Models a patient player who plans ahead.

**PriorityList** — Follows a designer-specified purchase order.
- Given a list of element IDs (possibly with count targets), buys them in order as they become affordable.
- Useful for testing a specific intended path through the game.

**Custom** — Accepts a callable for each of the three interface methods.
- The escape hatch for testing specific hypotheses.

**ClickProfile** helper (used by strategies for click modeling):
```python
ClickProfile(
    targets={"gold": 5.0},         # 5 CPS on gold
    active_until=Req.custom(        # stop clicking when gold rate > 10/sec
        lambda s: s.currency_rate("gold") > 10
    ),
    # Or: active_during_wait=True   # only click while waiting for a purchase
)
```

### 6.5 Terminal Conditions

```
TerminalCondition (interface):
    def is_met(self, state: GameState) -> bool

# Built-in:
Terminal.time(seconds=7200)                      # 2 hour simulation
Terminal.milestone("beat_final_boss")            # specific milestone reached
Terminal.currency("gold", ">=", 1e15)            # currency threshold
Terminal.all_purchased(tags=["tier1"])            # all tier1 elements bought
Terminal.stall(max_idle_seconds=600)              # 10min with no purchase = stall
Terminal.any(t1, t2, t3)                          # first condition met stops
Terminal.all(t1, t2)                              # all must be met
```

---

## 7. Pacing Analysis & Reporting

### 7.1 Tracked Metrics

The simulation records a time-series of game state snapshots and discrete events:

**Continuous (per tick or per event):**
- All currency values and rates over time
- Total elements owned over time

**Discrete events:**
- Each purchase: `(time, element_id, cost_paid, currencies_after)`
- Each milestone: `(time, milestone_id)`
- Each prestige: `(time, layer_id, reward_amount, run_duration)`
- Each stall: `(time, duration_until_next_purchase)`

**Derived metrics (computed from raw data):**
- **Time between purchases:** Distribution and max. Long gaps = boring waiting.
- **Purchase cadence curve:** Purchases per minute over time. Should ideally stay within a range.
- **Income growth curve:** How fast each currency's rate grows. Should be smooth, not staircase-with-long-flats.
- **Dead time ratio:** Fraction of total time where the player has no affordable purchase AND no meaningful click interaction. Should be minimized.
- **Milestone timing:** When each milestone is reached. Primary pacing validation data.
- **Stall events:** Any period where no progress is possible. Should be zero.
- **Effective CPS (choices per second):** How often the player has a meaningful decision. Proxy for engagement.

### 7.2 Pacing Bounds

Designers declare pacing expectations as **bounds**. The simulation checks these and reports pass/fail.

```
PacingBound:
    description: str
    condition: Callable[[SimulationReport], bool]
    severity: "error" | "warning"

# Convenience constructors:
PacingBound.milestone_between("first_upgrade", min_sec=5, max_sec=30)
PacingBound.milestone_between("prestige_available", min_sec=600, max_sec=1800)
PacingBound.max_gap_between_purchases(max_sec=120, after_time=60)
    # After the first minute, never go more than 2min without a purchase
PacingBound.no_stalls()
PacingBound.dead_time_ratio(max_ratio=0.30)
    # No more than 30% of play time should be "dead"
PacingBound.custom(lambda report: report.total_time < 14400, "Game completable in 4 hours")
```

### 7.3 Reports & Visualization

**Text Report (console):**
```
═══ IdleEngine Simulation Report ═══
Strategy: GreedyCheapest (5 CPS until rate>10)
Terminal: milestone("endgame") OR time(7200)
Result: Reached "endgame" at 4832.0s

MILESTONES:
  ✓ first_upgrade .............. 12.0s   [bound: 5-30s]
  ✓ ten_farms .................. 187.0s  [bound: 120-300s]
  ✗ prestige_available ......... 2451.0s [bound: 600-1800s] ← OVER BY 651s
  ✓ endgame .................... 4832.0s [bound: 3600-7200s]

PACING:
  ✓ Max purchase gap: 98s (limit: 120s after 60s)
  ✓ No stalls detected
  ✗ Dead time ratio: 0.37 (limit: 0.30) ← 37% dead time

SUMMARY: 1 error, 1 warning — NEEDS REBALANCING
```

**Data Export:** Raw CSV/JSON of time-series data for external analysis.

**Matplotlib Visualization** (optional, since we're in Python):
- Currency values over time (log scale)
- Production rates over time
- Purchase timeline (scatter plot: time vs element, colored by category)
- Gap-between-purchases histogram
- Overlay of milestone bounds as shaded regions

The report system is designed so that a designer can run `python -m idleengine.simulate my_game.py` and immediately see whether their balance is in the right ballpark.

---

## 8. Presentation Layer (PyGame)

### 8.1 Decoupled Architecture

The presenter **reads** `GameState` and **writes** player actions to `GameRuntime`. It has zero game logic.

```
GamePresenter:
    def __init__(self, runtime: GameRuntime, layout: UILayout)
    
    # Main loop (called by PyGame):
    def update(self, delta):
        runtime.tick(delta)
        self.refresh_ui(runtime.get_state())
    
    def handle_event(self, event):
        # Map clicks to runtime.try_purchase(), runtime.process_click(), etc.
```

### 8.2 UI Component Library

Since idle games share common UI patterns, the engine provides reusable PyGame widgets:

- **CurrencyDisplay**: Shows currency name, current value, rate (`Gold: 1,234 (+56/sec)`)
- **ElementButton**: Shows element name, cost, count, description. Grayed when locked/unaffordable. Click to purchase.
- **ProgressBar**: Generic bar widget (for caps, timers, progress)
- **TabContainer**: Organize elements into tabs/categories
- **TooltipOverlay**: Hover info
- **MilestonePopup**: Notification when milestone reached
- **PrestigePanel**: Shows prestige reward preview and reset button

These are **optional** — a game can ignore them entirely and render custom PyGame surfaces. But for rapid prototyping, they let you go from game definition to playable prototype with minimal UI code.

### 8.3 Layout Definition

```
UILayout:
    panels: list[Panel]
    
Panel:
    region: Rect                           # screen area
    type: "currencies" | "elements" | "custom"
    filter: Callable | tag filter          # which elements/currencies to show
    sort: str                              # "cost", "name", "category"
    renderer: Callable | None              # custom render override
```

### 8.4 Debug Overlay

Toggle-able overlay showing:
- All production rates and their effect breakdowns
- Current simulation metrics (if running alongside)
- Time controls (pause, 2x, 10x, 100x speed)
- "Sim to here" button: run simulation from current state to see future pacing

---

## 9. Game Definition Workflow

### Step-by-step for a new game prototype:

```
1. Create a Python module: my_game.py
2. Define currencies
3. Define elements (with effects, costs, requirements)
4. Define milestones (pacing markers)
5. Define prestige layers (if any)
6. Define pacing bounds (expected timeline)
7. Run simulation:
   $ python -m idleengine.simulate my_game --strategy greedy_cheapest
   → Get instant pacing report
   → Iterate on numbers until bounds are satisfied
8. Build UI layout (or use auto-layout)
9. Run interactive prototype:
   $ python -m idleengine.play my_game
   → Playtest for "feel" — the hard numbers are already validated
```

### Game Definition Module Contract

A game definition module exports a function:

```python
def define_game() -> GameDefinition:
    ...
```

This returns the complete `GameDefinition` object. The simulation runner and the interactive player both call this function.

---

## 10. Example: Minimal Game Definition (Pseudo-Python)

```python
def define_game() -> GameDefinition:
    return GameDefinition(
        config=GameConfig(
            name="Cookie Example",
            tick_rate=10,  # 10 ticks per second in interactive mode
        ),
        
        currencies=[
            Currency("cookies", display="Cookies", initial=0),
            Currency("prestige_chips", display="Prestige Chips", 
                     initial=0, persistent=True),
        ],
        
        elements=[
            Element(
                id="cursor",
                display="Cursor",
                base_cost={"cookies": 15},
                cost_scaling=CostScaling.exponential(1.15),
                max_count=None,
                effects=[
                    Effect.per_count("cursor", PRODUCTION_FLAT, "cookies", 0.1),
                ],
                requirements=[],
            ),
            Element(
                id="grandma",
                display="Grandma",
                base_cost={"cookies": 100},
                cost_scaling=CostScaling.exponential(1.15),
                max_count=None,
                effects=[
                    Effect.per_count("grandma", PRODUCTION_FLAT, "cookies", 1.0),
                ],
                requirements=[Req.count("cursor", ">=", 1)],
            ),
            Element(
                id="farm",
                display="Farm",
                base_cost={"cookies": 1100},
                cost_scaling=CostScaling.exponential(1.15),
                max_count=None,
                effects=[
                    Effect.per_count("farm", PRODUCTION_FLAT, "cookies", 8.0),
                ],
                requirements=[Req.count("grandma", ">=", 1)],
            ),
            Element(
                id="double_cookies",
                display="Cookie Doubler",
                base_cost={"cookies": 500},
                cost_scaling=CostScaling.fixed(),
                max_count=1,
                effects=[
                    Effect.static(PRODUCTION_MULT, "cookies", 2.0),
                ],
                requirements=[Req.total_earned("cookies", ">=", 1000)],
                tags={"upgrade"},
            ),
            Element(
                id="grandma_synergy",
                display="Grandma's Secret Recipe",
                base_cost={"cookies": 5000},
                cost_scaling=CostScaling.fixed(),
                max_count=1,
                effects=[
                    # Each grandma gets +1% production per farm
                    Effect(
                        type=PRODUCTION_FLAT,
                        target="cookies",
                        value=lambda s: (
                            s.element_count("grandma") * 
                            s.element_count("farm") * 0.05
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
            Milestone("first_purchase", "First generator bought",
                      trigger=Req.custom(lambda s: 
                          s.element_count("cursor") + 
                          s.element_count("grandma") + 
                          s.element_count("farm") >= 1
                      )),
            Milestone("hundred_cps", "100 cookies/sec",
                      trigger=Req.custom(lambda s: s.currency_rate("cookies") >= 100)),
            Milestone("million_cookies", "1M cookies earned",
                      trigger=Req.total_earned("cookies", ">=", 1_000_000)),
        ],
        
        prestige_layers=[
            PrestigeLayer(
                id="prestige",
                prestige_currency="prestige_chips",
                reward_formula=lambda s: math.floor(
                    s.total_earned("cookies") / 1_000_000
                ) ** 0.5,
                currencies_reset=["cookies"],
                elements_reset=["cursor", "grandma", "farm", 
                               "double_cookies", "grandma_synergy"],
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
```

This single file is enough to:
1. Run automated pacing simulation with any strategy
2. Generate a playable PyGame prototype (with default or custom layout)
3. Iterate on numbers and immediately re-validate

---

## 11. Extension Points

### 11.1 Custom Effect Types
Register new effect types with a handler function:
```python
engine.register_effect_type("DAMAGE", handler=my_damage_handler)
```
The handler receives `(effect, state, delta)` and mutates state as needed.

### 11.2 Custom Production Pipelines
Override the default 4-phase pipeline with a custom computation:
```python
engine.set_production_pipeline("mana", custom_mana_pipeline_fn)
```

### 11.3 Subsystems
For mechanics that don't fit the currency/element model (combat, exploration, crafting queues), define a **Subsystem**:
```python
class CombatSubsystem(Subsystem):
    def tick(self, state, delta): ...
    def get_simulation_proxy(self) -> SimulationProxy: ...
```
The `SimulationProxy` provides the simulation with a simplified model of the subsystem's behavior (e.g., "combat grants X gold every Y seconds on average").

### 11.4 Data-Driven Definitions
A future layer could load game definitions from YAML/JSON for the simple cases, with Python callbacks referenced by name for complex logic.

### 11.5 Monte Carlo Mode
Run N simulations with randomized `estimated_time` requirements and/or the `RandomStrategy`, producing statistical distributions of pacing metrics rather than single-run results. Useful for games with significant variance in progression paths.

---

## 12. Open Questions & Future Considerations

| Question | Current Thinking |
|---|---|
| **Spatial/positional mechanics** (factory placement, territory) | Out of scope for core engine. Model as subsystem with simulation proxy. |
| **Narrative/branching** | Model as elements with mutually exclusive requirements. Simulation could test each branch. |
| **Real-time elements** (timers, cooldowns) | Support in core: `Element.cooldown: float`. Runtime tracks last-purchase time. Simulation respects cooldown. |
| **Offline progress** | `GameRuntime.apply_offline(seconds)` uses the same tick logic. Could share the simulation's event-jump mode for efficiency. |
| **Save/Load** | `GameState` is fully serializable (it's just numbers and IDs). Callables in definitions aren't serialized — they're reconstructed from the definition module. |
| **Multi-strategy comparative reports** | Run same game with multiple strategies, overlay results. "How much does optimal play differ from greedy?" If the gap is enormous, the game may be too punishing for casual players. |
| **Strategy discovery / genetic algorithms** | Non-goal currently, but the strategy interface is clean enough that someone could plug in ML. |
| **Tick rate sensitivity** | Should validate that simulation results are stable across different tick resolutions. Include as automated check. |

---

## 13. Summary

IdleEngine's value proposition is the **feedback loop speed**. Today, idle game balance is validated by playing the game for hours or by spreadsheet math that doesn't capture emergent interactions between systems. IdleEngine closes that loop:

```
Define game → Simulate (seconds) → Read pacing report → Adjust numbers → Repeat
```

Human QA becomes about **feel, juice, surprise, and delight** — things machines can't evaluate — while the tedious question of "does the pacing math work out" is answered by the machine in seconds, every time, for every change.

The architecture ensures this isn't throw-away scaffolding: the same `GameDefinition` and `GameRuntime` that drive simulation are the ones that drive the actual game. There is no translation layer, no "simulation version" that can drift from reality. If the simulation says pacing is good, the game's pacing *is* good — modulo the strategy's fidelity to real player behavior, which is why we support multiple strategies and configurable click profiles.