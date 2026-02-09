from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

from idleengine.requirement import Requirement

if TYPE_CHECKING:
    from idleengine.state import GameState


@dataclass
class MilestoneDef:
    """A named one-time event that fires when its trigger is met."""

    id: str
    description: str = ""
    trigger: Requirement | None = None
    on_trigger: Callable[[GameState], None] | None = None
    pacing_note: str | None = None
