"""Tests for cost_scaling module."""
import pytest

from idleengine.cost_scaling import CostScaling


def test_fixed():
    cs = CostScaling.fixed()
    base = {"gold": 100.0, "gems": 5.0}
    assert cs.compute(base, 0) == {"gold": 100.0, "gems": 5.0}
    assert cs.compute(base, 10) == {"gold": 100.0, "gems": 5.0}


def test_exponential():
    cs = CostScaling.exponential(2.0)
    base = {"gold": 100.0}
    assert cs.compute(base, 0) == {"gold": 100.0}
    assert cs.compute(base, 1) == {"gold": 200.0}
    assert cs.compute(base, 2) == {"gold": 400.0}
    assert cs.compute(base, 3) == {"gold": 800.0}


def test_exponential_default_rate():
    cs = CostScaling.exponential()
    base = {"gold": 100.0}
    cost_1 = cs.compute(base, 1)["gold"]
    assert abs(cost_1 - 115.0) < 0.01


def test_linear():
    cs = CostScaling.linear(0.10)
    base = {"gold": 100.0}
    assert cs.compute(base, 0)["gold"] == pytest.approx(100.0)
    assert cs.compute(base, 1)["gold"] == pytest.approx(110.0)
    assert cs.compute(base, 5)["gold"] == pytest.approx(150.0)


def test_custom():
    def my_fn(base, count):
        return {k: v * (count + 1) ** 2 for k, v in base.items()}

    cs = CostScaling.custom(my_fn)
    base = {"gold": 10.0}
    assert cs.compute(base, 0) == {"gold": 10.0}
    assert cs.compute(base, 1) == {"gold": 40.0}
    assert cs.compute(base, 2) == {"gold": 90.0}
