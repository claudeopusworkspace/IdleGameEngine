# Common Pitfalls

Hard-won lessons from building idle games with IdleEngine.

## 1. per_count() with Multiplicative Effects

**The trap:** Using `Effect.per_count()` with `PRODUCTION_MULT` or `GLOBAL_MULT`.

```python
# DON'T DO THIS
Effect.per_count("forge", EffectType.PRODUCTION_MULT, "gold", 1.05)
```

This creates a value function that returns `count * 1.05`. Since `PRODUCTION_MULT` values are **multiplied together** in the pipeline:

| Count | Multiplier | What it does |
|---|---|---|
| 1 | 1.05 | 5% boost (looks right!) |
| 2 | 2.10 | **Doubles** production (almost certainly not intended) |
| 3 | 3.15 | **Triples** production |
| 10 | 10.50 | 10x production |

What you almost certainly wanted was **exponential compounding**: `1.05^count`.

**The fix:** Use `per_count_exponential()`:

```python
# DO THIS INSTEAD
Effect.per_count_exponential("forge", EffectType.PRODUCTION_MULT, "gold", 1.05)
```

| Count | Multiplier | What it does |
|---|---|---|
| 1 | 1.05 | 5% boost |
| 2 | 1.1025 | 10.25% boost |
| 3 | 1.1576 | 15.76% boost |
| 10 | 1.6289 | 62.89% boost |

`GameDefinition.validate()` will warn if it detects this pattern.

`per_count()` is perfectly fine for `PRODUCTION_FLAT` (the most common use case — "each miner produces 5 gold/sec").

## 2. Hard Caps on Input Currencies

**The trap:** Capping a primary production currency where the only way to raise the cap costs that same currency with exponential scaling.

```python
# Dangerous pattern:
CurrencyDef("mana", cap=lambda s: 100 + s.element_count("mana_pool") * 50)

ElementDef(
    "mana_pool",
    base_cost={"mana": 100},
    cost_scaling=CostScaling.exponential(1.5),  # cost grows 1.5x each purchase
    effects=[...],  # only raises the cap by +50
)
```

The exponential cost always eventually exceeds the linear cap growth. At some point, the next mana pool costs more mana than the player can ever hold, creating an **unresolvable progression wall**.

**The fix:** Prefer uncapped currencies with spending pressure from opportunity cost. If you need caps, ensure the cap growth outpaces the cost growth, or provide alternative ways to raise the cap.

## 3. Flat Additive Prestige Rewards

**The trap:** Prestige rewards that add small flat production bonuses.

```python
# Weak prestige reward:
ElementDef(
    "prestige_bonus",
    effects=[
        Effect.static(EffectType.PRODUCTION_FLAT, "gold", 10.0),  # +10 gold/sec per prestige point
    ],
)
```

By the time a player prestiges, they've likely reached hundreds or thousands of gold/sec through multiplicative compounding. A flat +10/sec is meaningless — it doesn't make the player feel powerful from the start of the new run.

**The fix:** Prestige should grant **multiplicative global bonuses** so the player feels the impact immediately:

```python
# Strong prestige reward:
Effect.per_count_exponential("prestige_bonus", EffectType.GLOBAL_MULT, "gold", 1.25)
# Each prestige point gives 1.25x ALL production — player starts each run noticeably stronger
```

## 4. Forced Prestige via Subsystems

**The trap:** Subsystems that automatically call `trigger_prestige()` when a threshold is reached.

```python
# Removes player agency:
class AutoPrestigeSubsystem(Subsystem):
    def tick(self, delta, runtime):
        if runtime.get_state().currency_value("corruption") >= 100:
            runtime.trigger_prestige("cleanse")  # forced reset!
```

This eliminates the strategic decision of "quick run for small reward vs. deep run for big reward." Forced prestige feels like punishment, not a meaningful choice.

**The fix:** If you want pressure toward prestige, make it a risk/reward trade-off the player controls:

- Increasing corruption could **reduce** production rates (multiplicative penalty), making the run progressively less efficient
- Show the player their potential prestige reward and let them choose when to reset
- Use milestones and UI indicators to nudge, not force
