# API Reference

Condensed reference for all public classes and functions. Import everything from the top-level package:

```python
from idleengine import *
```

---

## Game Definition

### `GameConfig(name="Untitled", tick_rate=10)`

Top-level game configuration.

### `GameDefinition(config, currencies, elements, milestones, prestige_layers, pacing_bounds, click_targets)`

Complete static definition of a game. All list arguments default to empty.

- `.validate() -> list[str]` — returns error messages (empty = valid)
- `.get_currency(id)`, `.get_element(id)`, `.get_milestone(id)`, `.get_prestige_layer(id)`, `.get_click_target(currency)` — O(1) lookups, return `None` if not found

### `CurrencyDef(id, display_name="", initial_value=0.0, cap=None, persistent=False, hidden_until=None)`

### `ElementDef(id, display_name="", description="", base_cost={}, cost_scaling, max_count=None, effects=[], requirements=[], purchase_requirements=[], on_purchase=None, tags=set(), category="")`

### `MilestoneDef(id, description="", trigger=None, on_trigger=None, pacing_note=None)`

### `PrestigeLayerDef(id, prestige_currency="", reward_formula=None, currencies_reset=[], elements_reset=[], requirements=[], minimum_reward=0.0)`

### `ClickTarget(currency="", base_value=1.0)`

---

## Cost Scaling

### `CostScaling`

- `.fixed()` — constant cost
- `.exponential(growth_rate=1.15)` — `base * growth_rate^count`
- `.linear(increment_pct=0.10)` — `base * (1 + pct * count)`
- `.custom(fn)` — `fn(base_cost_dict, count) -> cost_dict`

All are classmethods returning a `CostScaling` instance.

---

## Effects

### `EffectType` (enum)

`PRODUCTION_FLAT`, `PRODUCTION_ADD_PCT`, `PRODUCTION_MULT`, `GLOBAL_MULT`, `CLICK_FLAT`, `CLICK_MULT`, `COST_MULT`, `CAP_FLAT`, `CAP_MULT`, `AUTO_CLICK`, `GRANT`, `UNLOCK`, `CUSTOM`

### `EffectDef(type, target, value=0.0, condition=None, phase=None)`

- `value` — `float` or `Callable[[GameState], float]`
- `condition` — `Requirement | None`, effect only active when true
- `phase` — defaults based on type; override for custom pipeline ordering

### `Effect` (convenience constructors)

- `Effect.per_count(element, type, target, per_unit, condition=None)` — value = `element_count * per_unit`
- `Effect.static(type, target, value, condition=None)` — constant value
- `Effect.synergy(source, type, target, per_unit, condition=None)` — value = `source_count * per_unit`

---

## Requirements

### `Requirement` (ABC)

- `.evaluate(state) -> bool`
- Supports `&` (AND) and `|` (OR) operators

### `Req` (factory)

| Method | True when |
|---|---|
| `Req.resource(currency, op, threshold)` | current value matches |
| `Req.total_earned(currency, op, threshold)` | lifetime total matches |
| `Req.owns(element)` | count >= 1 |
| `Req.count(element, op, threshold)` | count matches |
| `Req.milestone(id)` | milestone has fired |
| `Req.time(op, seconds)` | game time matches |
| `Req.all(*reqs)` | all true |
| `Req.any(*reqs)` | any true |
| `Req.custom(fn)` | `fn(state)` returns `True` |
| `Req.estimated_time(mean, variance, description)` | simulation time sampling |

Operators: `">=", "<=", ">", "<", "==", "!="`

---

## Runtime

### `GameRuntime(definition)`

Validates definition and creates initial game state.

**Core loop:**
- `.tick(delta_seconds)` — advance time, apply production, check milestones
- `.try_purchase(element_id) -> bool` — attempt purchase, returns success
- `.process_click(target_currency) -> float` — process click, returns amount earned
- `.trigger_prestige(layer_id) -> PrestigeResult` — trigger prestige reset

**Queries:**
- `.get_state() -> GameState` — live reference (not a copy)
- `.get_available_purchases() -> list[ElementStatus]` — elements with requirements met
- `.get_affordable_purchases() -> list[ElementStatus]` — available AND affordable
- `.compute_current_cost(element_id) -> dict[str, float]`
- `.compute_time_to_afford(element_id) -> float | None` — seconds, or None if impossible

**Extension:**
- `.register_effect_type(name, handler)`
- `.set_production_pipeline(currency_id, fn)`
- `.add_subsystem(subsystem)`

### `GameState`

- `.time_elapsed: float`
- `.currencies: dict[str, CurrencyState]`
- `.elements: dict[str, ElementState]`
- `.milestones_reached: dict[str, float]` — id -> time
- `.prestige_counts: dict[str, int]`
- `.run_number: int`
- `.currency_value(id) -> float`
- `.currency_rate(id) -> float`
- `.element_count(id) -> int`
- `.has_milestone(id) -> bool`
- `.total_earned(id) -> float`

### `PrestigeResult` (frozen dataclass)

- `.success: bool`
- `.reward_amount: float`
- `.currencies_reset: list[str]`
- `.elements_reset: list[str]`
- `.reason: str`

### `ElementStatus` (frozen dataclass)

- `.id`, `.display_name`, `.count`, `.available`, `.affordable`
- `.current_cost: dict[str, float]`
- `.max_count: int | None`
- `.category: str`, `.tags: frozenset[str]`

---

## Simulation

### `Simulation(definition, strategy, terminal, tick_resolution=1.0, seed=None, mode="tick")`

- `.run() -> SimulationReport`

### `SimulationReport`

Fields: `strategy_description`, `terminal_description`, `outcome`, `total_time`, `currency_snapshots`, `purchases`, `milestones`, `prestiges`, `stalls`, `milestone_times`, `purchase_gaps`, `max_purchase_gap`, `mean_purchase_gap`, `dead_time_ratio`, `purchases_per_minute`

Methods: `.milestone_time(id)`, `.currency_series(id)`, `.rate_series(id)`

---

## Strategies

### `Strategy` (ABC)

- `.decide_purchases(state, affordable) -> list[str]`
- `.get_clicks(state, duration, is_waiting=False) -> dict[str, int]`
- `.should_prestige(state, layer_id) -> bool`
- `.describe() -> str`

### Built-in Strategies

| Class | Behavior |
|---|---|
| `GreedyCheapest(click_profile, prestige_mode, cost_weights)` | Buy cheapest first |
| `GreedyROI(runtime, click_profile, prestige_mode)` | Buy best ROI first |
| `SaveForBest(runtime, click_profile)` | Save for highest-ROI available element |
| `PriorityList(priorities, fallback, click_profile)` | Follow designer order |
| `CustomStrategy(decide_fn, clicks_fn, prestige_fn, name)` | Arbitrary callables |

### `ClickProfile(targets={}, active_until=None, active_during_wait=False)`

- `targets` — `{currency_id: clicks_per_second}`
- `active_until` — `Requirement` that stops clicking when met
- `active_during_wait` — if `True`, clicks continue during event-jump waits

---

## Terminal Conditions

### `Terminal` (factory)

| Method | Stops when |
|---|---|
| `Terminal.time(seconds)` | Time elapsed |
| `Terminal.milestone(id)` | Milestone reached |
| `Terminal.currency(id, op, threshold)` | Currency threshold |
| `Terminal.all_purchased(element_ids=[...])` | All elements owned |
| `Terminal.stall(max_idle_seconds)` | No purchase for N seconds |
| `Terminal.any(*conditions)` | Any met |
| `Terminal.all(*conditions)` | All met |

---

## Pacing

### `PacingBound(description, condition, severity="error", detail=None)`

- `.evaluate(report) -> PacingBoundResult`

**Convenience constructors:**

| Method | Check |
|---|---|
| `PacingBound.milestone_between(id, min, max)` | Milestone time in range |
| `PacingBound.max_gap_between_purchases(max, after_time)` | No long waits |
| `PacingBound.no_stalls()` | Zero stalls |
| `PacingBound.dead_time_ratio(max_ratio)` | Limited dead time |
| `PacingBound.custom(fn, description)` | Arbitrary check |

---

## Output

### `format_text_report(report, bounds=None) -> str`

Console-formatted pacing report.

### `export_csv(report, path_prefix)`

Creates `{prefix}_currencies.csv`, `{prefix}_purchases.csv`, `{prefix}_milestones.csv`.

### `export_json(report, path)`

Full report as JSON.

### `plot_simulation(report, output_path=None)`

4-panel matplotlib chart. Requires `idleengine[viz]`. Pass `None` to show interactively.
