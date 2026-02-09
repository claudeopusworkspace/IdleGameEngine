from __future__ import annotations

from typing import Callable


class CostScaling:
    """Determines how element costs change with purchase count."""

    def __init__(self, fn: Callable[[dict[str, float], int], dict[str, float]]) -> None:
        self._fn = fn

    def compute(self, base_cost: dict[str, float], current_count: int) -> dict[str, float]:
        return self._fn(base_cost, current_count)

    @classmethod
    def fixed(cls) -> CostScaling:
        """Cost never changes."""
        return cls(lambda base, _count: dict(base))

    @classmethod
    def exponential(cls, growth_rate: float = 1.15) -> CostScaling:
        """Cost = base * growth_rate^count."""
        gr = growth_rate  # capture

        def _compute(base: dict[str, float], count: int) -> dict[str, float]:
            mult = gr ** count
            return {k: v * mult for k, v in base.items()}

        return cls(_compute)

    @classmethod
    def linear(cls, increment_pct: float = 0.10) -> CostScaling:
        """Cost = base * (1 + increment_pct * count)."""
        pct = increment_pct

        def _compute(base: dict[str, float], count: int) -> dict[str, float]:
            mult = 1.0 + pct * count
            return {k: v * mult for k, v in base.items()}

        return cls(_compute)

    @classmethod
    def custom(cls, fn: Callable[[dict[str, float], int], dict[str, float]]) -> CostScaling:
        """Arbitrary cost function."""
        return cls(fn)
