from __future__ import annotations

import operator
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from idleengine.state import GameState

DynamicFloat = float | Callable[['GameState'], float]
DynamicOptionalFloat = float | Callable[['GameState'], float] | None
DynamicStr = str | Callable[['GameState'], str]

_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}


def resolve_value(value: DynamicFloat, state: GameState) -> float:
    """Resolve a literal float or a callable that takes GameState."""
    if callable(value):
        return value(state)
    return value


def resolve_optional(value: DynamicOptionalFloat, state: GameState) -> float | None:
    """Resolve a value that may be None."""
    if value is None:
        return None
    if callable(value):
        return value(state)
    return value


def resolve_str(value: DynamicStr, state: GameState) -> str:
    """Resolve a literal string or a callable that takes GameState."""
    if callable(value):
        return value(state)
    return value


def compare(left: float, op: str, right: float) -> bool:
    """Compare two values using a string operator."""
    fn = _OPS.get(op)
    if fn is None:
        raise ValueError(f"Unknown operator: {op!r}. Expected one of {list(_OPS)}")
    return fn(left, right)
