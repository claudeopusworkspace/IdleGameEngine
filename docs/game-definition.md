# Game Definition Reference

Everything you can configure in a `GameDefinition`.

## GameConfig

```python
GameConfig(
    name="My Game",    # display name
    tick_rate=10,      # ticks/sec for interactive mode (simulation ignores this)
)
```

## CurrencyDef

A currency is any tracked numeric quantity.

```python
CurrencyDef(
    id="gold",                    # unique identifier (required)
    display_name="Gold",          # for UI (defaults to id)
    initial_value=0.0,            # starting amount
    cap=None,                     # max value, None = uncapped
    persistent=False,             # if True, survives prestige resets
    hidden_until=None,            # Requirement — hidden in UI until met
)
```

### Dynamic caps

`cap` accepts a literal float or a callable:

```python
CurrencyDef("mana", cap=lambda s: 100 + s.element_count("mana_pool") * 50)
```

The runtime resolves the cap each tick.

## ElementDef

An element is anything the player can buy: generators, upgrades, one-time unlocks.

```python
ElementDef(
    id="farm",                        # unique identifier (required)
    display_name="Farm",              # for UI
    description="Produces 8 gold/s",  # can be a callable for dynamic text
    base_cost={"gold": 1100},         # currency_id -> amount
    cost_scaling=CostScaling.exponential(1.15),
    max_count=None,                   # None = unlimited, 1 = one-time
    effects=[...],                    # list of EffectDef
    requirements=[...],               # visibility requirements
    purchase_requirements=[...],      # additional buy-time checks
    on_purchase=None,                 # callback: fn(state) -> None
    tags=set(),                       # for filtering/grouping
    category="",                      # UI section
)
```

### Cost Scaling

Controls how cost changes each time the player buys another copy:

| Method | Formula | Use Case |
|---|---|---|
| `CostScaling.fixed()` | Always base cost | One-time upgrades |
| `CostScaling.exponential(1.15)` | `base * 1.15^count` | Standard generators |
| `CostScaling.linear(0.10)` | `base * (1 + 0.10 * count)` | Gentle scaling |
| `CostScaling.custom(fn)` | `fn(base_dict, count) -> dict` | Anything |

### Requirements vs Purchase Requirements

- **`requirements`** — Must ALL be met for the element to appear as available. Controls visibility.
- **`purchase_requirements`** — Must ALL be met at buy time, in addition to affordability. Use for extra gating beyond visibility.

### Tags

Tags are arbitrary strings. The engine uses one special tag:

- `"persistent"` — Elements with this tag are **not** reset during prestige, even if listed in the prestige layer's reset list.

## EffectDef and EffectType

Effects define what owning an element does. Every effect has a type, a target, and a value.

### Effect Types

| Type | Target | What it does |
|---|---|---|
| `PRODUCTION_FLAT` | currency id | Adds flat production/sec |
| `PRODUCTION_ADD_PCT` | currency id | Adds additive % to production (0.5 = +50%) |
| `PRODUCTION_MULT` | currency id | Multiplies production |
| `GLOBAL_MULT` | (any) | Multiplies ALL currency production |
| `CLICK_FLAT` | currency id | Adds flat value to clicks |
| `CLICK_MULT` | currency id | Multiplies click value |
| `COST_MULT` | element id | Multiplies cost of target element |
| `CAP_FLAT` | currency id | Adds to currency cap |
| `CAP_MULT` | currency id | Multiplies currency cap |
| `AUTO_CLICK` | currency id | Generates auto-clicks/sec |
| `GRANT` | currency id | One-time grant on purchase (immediate) |
| `UNLOCK` | element id | Makes target element available (immediate) |
| `CUSTOM` | (any) | Custom handler registered with runtime |

### The Production Pipeline

For each currency, every tick:

```
rate = flat_sum * (1 + add_pct) * mult * global_mult
```

Where:
- `flat_sum` = sum of all `PRODUCTION_FLAT` effects targeting this currency
- `add_pct` = sum of all `PRODUCTION_ADD_PCT` effects targeting this currency
- `mult` = product of all `PRODUCTION_MULT` effects targeting this currency
- `global_mult` = product of all `GLOBAL_MULT` effects

### Convenience Constructors

```python
# Each miner produces 2 gold/sec (scales with count)
Effect.per_count("miner", EffectType.PRODUCTION_FLAT, "gold", 2.0)

# Flat x2 multiplier
Effect.static(EffectType.PRODUCTION_MULT, "gold", 2.0)

# +1% gold/sec per farm owned (synergy between elements)
Effect.synergy("farm", EffectType.PRODUCTION_ADD_PCT, "gold", 0.01)
```

### Dynamic Values

Any effect value can be a callable:

```python
EffectDef(
    type=EffectType.PRODUCTION_FLAT,
    target="gold",
    value=lambda s: s.element_count("miner") * s.element_count("forge") * 0.1,
)
```

### Conditional Effects

Effects can have a condition that must be met for them to activate:

```python
Effect.static(
    EffectType.PRODUCTION_MULT, "gold", 3.0,
    condition=Req.milestone("golden_age"),
)
```

## Requirements

Requirements are boolean conditions on game state. Used for element visibility, milestones, prestige gating, and effect conditions.

### Built-in Types

```python
Req.resource("gold", ">=", 1000)          # current gold >= 1000
Req.total_earned("gold", ">=", 1e6)       # lifetime gold >= 1M
Req.owns("farm")                          # owns at least 1 farm
Req.count("farm", ">=", 10)               # owns >= 10 farms
Req.milestone("unlocked_lab")             # milestone has fired
Req.time(">=", 300)                       # game time >= 5 minutes
Req.all(req1, req2, req3)                 # all must be true
Req.any(req1, req2)                       # any must be true
Req.custom(lambda s: ...)                 # arbitrary logic
Req.estimated_time(120, variance=30)      # simulation-only time estimate
```

### Operators

Requirements support `&` and `|` for composition:

```python
req = Req.resource("gold", ">=", 100) & Req.owns("farm")
req = Req.count("miner", ">=", 5) | Req.milestone("shortcut")
```

### Estimated Time (Simulation Only)

For events that can't be simulated deterministically (boss kills, puzzles, exploration), specify an expected duration:

```python
Req.estimated_time(mean=120, variance=30, description="Beat the dragon")
```

During simulation, this samples from a normal distribution. During real gameplay, replace with actual game logic.

## MilestoneDef

One-time events that fire when their trigger is met.

```python
MilestoneDef(
    id="first_farm",                              # unique id
    description="Built first farm",               # display text
    trigger=Req.owns("farm"),                     # when to fire
    on_trigger=lambda s: ...,                     # optional callback
    pacing_note="Should happen around 2 minutes", # design intent
)
```

Milestones are tracked by simulation as timestamps — they're the primary data for pacing analysis.

## PrestigeLayerDef

Defines a reset mechanic (prestige, transcendence, etc.).

```python
PrestigeLayerDef(
    id="prestige",
    prestige_currency="prestige_points",
    reward_formula=lambda s: math.floor(s.total_earned("gold") / 1e6) ** 0.5,
    currencies_reset=["gold", "gems"],        # or "all_non_persistent"
    elements_reset=["miner", "upgrade_1"],    # or "all_non_persistent"
    requirements=[Req.total_earned("gold", ">=", 1_000_000)],
    minimum_reward=1.0,    # don't allow prestige for less than 1 point
)
```

- `currencies_reset` / `elements_reset` — List of IDs or the string `"all_non_persistent"` to reset everything not marked persistent.
- Elements with `"persistent"` in their tags are never reset, even if listed.
- Currencies reset to their `initial_value`.

## ClickTarget

Declares that a currency can be earned by clicking:

```python
ClickTarget("gold", base_value=1.0)
```

Click value is modified by `CLICK_FLAT` and `CLICK_MULT` effects.

## GameDefinition

Combines everything:

```python
GameDefinition(
    config=GameConfig(...),
    currencies=[...],
    elements=[...],
    milestones=[...],
    prestige_layers=[...],
    pacing_bounds=[...],
    click_targets=[...],
)
```

Call `definition.validate()` to check for errors (dangling references, duplicate IDs, etc.). `GameRuntime` calls this automatically on construction.

## Lookup Methods

`GameDefinition` provides O(1) lookups:

```python
definition.get_currency("gold")       # -> CurrencyDef | None
definition.get_element("miner")       # -> ElementDef | None
definition.get_milestone("first")     # -> MilestoneDef | None
definition.get_prestige_layer("p1")   # -> PrestigeLayerDef | None
definition.get_click_target("gold")   # -> ClickTarget | None
```
