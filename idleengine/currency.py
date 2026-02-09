from __future__ import annotations

from dataclasses import dataclass, field

from idleengine._types import DynamicOptionalFloat
from idleengine.requirement import Requirement


@dataclass
class CurrencyDef:
    """Static definition of a currency."""

    id: str
    display_name: str = ""
    initial_value: float = 0.0
    cap: DynamicOptionalFloat = None
    persistent: bool = False
    hidden_until: Requirement | None = None

    def __post_init__(self) -> None:
        if not self.display_name:
            self.display_name = self.id


@dataclass
class CurrencyState:
    """Mutable runtime state for a currency."""

    current: float = 0.0
    total_earned: float = 0.0
    current_rate: float = 0.0
