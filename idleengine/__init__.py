# idleengine — Generic Idle Game Engine & Automated Balance Simulation

from idleengine._types import DynamicFloat, DynamicStr, resolve_value, compare
from idleengine.requirement import Requirement, Req, EstimatedTimeRequirement
from idleengine.cost_scaling import CostScaling
from idleengine.effect import EffectType, EffectPhase, EffectDef, Effect
from idleengine.currency import CurrencyDef, CurrencyState
from idleengine.element import ElementDef, ElementState, ElementStatus
from idleengine.milestone import MilestoneDef
from idleengine.prestige import PrestigeLayerDef, PrestigeResult
from idleengine.definition import GameDefinition, GameConfig, ClickTarget
from idleengine.state import GameState
from idleengine.pipeline import ProductionPipeline
from idleengine.runtime import GameRuntime
from idleengine.subsystem import Subsystem, SimulationProxy
from idleengine.terminal import TerminalCondition, Terminal, SimulationContext
from idleengine.strategy import (
    Strategy,
    ClickProfile,
    GreedyCheapest,
    GreedyROI,
    SaveForBest,
    PriorityList,
    CustomStrategy,
)
from idleengine.metrics import MetricsCollector
from idleengine.simulation import Simulation
from idleengine.report import SimulationReport, build_report
from idleengine.pacing import PacingBound, PacingBoundResult
from idleengine.formatting import format_text_report

__all__ = [
    # Types
    "DynamicFloat",
    "DynamicStr",
    "resolve_value",
    "compare",
    # Requirements
    "Requirement",
    "Req",
    "EstimatedTimeRequirement",
    # Cost
    "CostScaling",
    # Effects
    "EffectType",
    "EffectPhase",
    "EffectDef",
    "Effect",
    # Data model
    "CurrencyDef",
    "CurrencyState",
    "ElementDef",
    "ElementState",
    "ElementStatus",
    "MilestoneDef",
    "PrestigeLayerDef",
    "PrestigeResult",
    # Definition
    "GameDefinition",
    "GameConfig",
    "ClickTarget",
    # State
    "GameState",
    # Pipeline
    "ProductionPipeline",
    # Runtime
    "GameRuntime",
    # Subsystem
    "Subsystem",
    "SimulationProxy",
    # Terminal
    "TerminalCondition",
    "Terminal",
    "SimulationContext",
    # Strategy
    "Strategy",
    "ClickProfile",
    "GreedyCheapest",
    "GreedyROI",
    "SaveForBest",
    "PriorityList",
    "CustomStrategy",
    # Simulation
    "MetricsCollector",
    "Simulation",
    "SimulationReport",
    "build_report",
    # Pacing
    "PacingBound",
    "PacingBoundResult",
    # Formatting
    "format_text_report",
]
