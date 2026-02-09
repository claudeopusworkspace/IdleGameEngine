"""Tests for _types module."""
import pytest

from idleengine._types import compare, resolve_value, resolve_str, resolve_optional


class FakeState:
    """Minimal stand-in for GameState."""
    def __init__(self):
        self.time_elapsed = 100.0


def test_resolve_value_literal():
    assert resolve_value(42.0, FakeState()) == 42.0


def test_resolve_value_callable():
    fn = lambda s: s.time_elapsed * 2
    assert resolve_value(fn, FakeState()) == 200.0


def test_resolve_str_literal():
    assert resolve_str("hello", FakeState()) == "hello"


def test_resolve_str_callable():
    fn = lambda s: f"time={s.time_elapsed}"
    assert resolve_str(fn, FakeState()) == "time=100.0"


def test_resolve_optional_none():
    assert resolve_optional(None, FakeState()) is None


def test_resolve_optional_float():
    assert resolve_optional(5.0, FakeState()) == 5.0


def test_resolve_optional_callable():
    assert resolve_optional(lambda s: 99.0, FakeState()) == 99.0


def test_compare_operators():
    assert compare(5, ">=", 3)
    assert compare(3, ">=", 3)
    assert not compare(2, ">=", 3)

    assert compare(3, "<=", 5)
    assert compare(3, "<=", 3)
    assert not compare(4, "<=", 3)

    assert compare(5, ">", 3)
    assert not compare(3, ">", 3)

    assert compare(3, "<", 5)
    assert not compare(3, "<", 3)

    assert compare(3, "==", 3)
    assert not compare(3, "==", 4)

    assert compare(3, "!=", 4)
    assert not compare(3, "!=", 3)


def test_compare_unknown_operator():
    with pytest.raises(ValueError, match="Unknown operator"):
        compare(1, "??", 2)
