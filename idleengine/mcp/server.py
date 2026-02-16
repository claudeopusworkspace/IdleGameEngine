"""MCP server wrapping GameRuntime for interactive AI playtesting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp.server.fastmcp import FastMCP

from idleengine._types import resolve_str
from idleengine.definition import GameDefinition
from idleengine.runtime import GameRuntime

# Maximum seconds per wait() call (24 hours)
_MAX_WAIT = 86400
# Maximum clicks per click() call
_MAX_CLICKS = 1000


@dataclass
class _GameHolder:
    """Holds the active game definition and runtime."""

    definition: GameDefinition
    runtime: GameRuntime
    _milestones_seen: set[str] = field(default_factory=set)


def _round_cost(cost: dict[str, float]) -> dict[str, float]:
    return {k: round(v, 2) for k, v in cost.items()}


# ── Tool logic functions (testable without MCP protocol) ────────────


def _tool_get_game_info(holder: _GameHolder) -> dict[str, Any]:
    defn = holder.definition
    return {
        "name": defn.config.name,
        "currencies": [
            {"id": c.id, "display_name": c.display_name}
            for c in defn.currencies
        ],
        "elements": [
            {"id": e.id, "display_name": e.display_name, "category": e.category}
            for e in defn.elements
        ],
        "milestones": [
            {"id": m.id, "description": m.description}
            for m in defn.milestones
        ],
        "click_targets": [
            {"currency": ct.currency, "base_value": ct.base_value}
            for ct in defn.click_targets
        ],
        "prestige_layers": [
            {"id": p.id, "prestige_currency": p.prestige_currency}
            for p in defn.prestige_layers
        ],
    }


def _tool_get_game_state(holder: _GameHolder) -> dict[str, Any]:
    state = holder.runtime.get_state()
    currencies = {}
    for cdef in holder.definition.currencies:
        cs = state.currencies[cdef.id]
        currencies[cdef.id] = {
            "display_name": cdef.display_name,
            "current": round(cs.current, 2),
            "total_earned": round(cs.total_earned, 2),
            "rate": round(cs.current_rate, 4),
        }
    elements = {}
    for edef in holder.definition.elements:
        es = state.elements[edef.id]
        elements[edef.id] = {
            "display_name": edef.display_name,
            "count": es.count,
            "available": es.available,
            "affordable": es.affordable,
        }
    return {
        "time_elapsed": round(state.time_elapsed, 2),
        "currencies": currencies,
        "elements": elements,
        "milestones_reached": list(state.milestones_reached.keys()),
        "prestige_counts": dict(state.prestige_counts),
        "run_number": state.run_number,
    }


def _tool_get_available_purchases(holder: _GameHolder) -> dict[str, Any]:
    purchases = holder.runtime.get_available_purchases()
    result = []
    for p in purchases:
        time_to_afford = holder.runtime.compute_time_to_afford(p.id)
        entry: dict[str, Any] = {
            "id": p.id,
            "display_name": p.display_name,
            "count": p.count,
            "affordable": p.affordable,
            "current_cost": _round_cost(p.current_cost),
            "category": p.category,
        }
        if p.max_count is not None:
            entry["max_count"] = p.max_count
        if time_to_afford is not None:
            entry["time_to_afford"] = round(time_to_afford, 2)
        else:
            entry["time_to_afford"] = None
        result.append(entry)
    return {"purchases": result}


def _tool_get_element_info(holder: _GameHolder, element_id: str) -> dict[str, Any]:
    edef = holder.definition.get_element(element_id)
    if edef is None:
        return {"error": f"Unknown element: {element_id!r}"}

    state = holder.runtime.get_state()
    es = state.elements[element_id]
    cost = holder.runtime.compute_current_cost(element_id)

    effects = []
    for eff in edef.effects:
        effects.append({
            "type": eff.type.name,
            "target": eff.target,
            "phase": eff.phase.name if eff.phase else None,
        })

    result: dict[str, Any] = {
        "id": edef.id,
        "display_name": edef.display_name,
        "description": resolve_str(edef.description, state),
        "category": edef.category,
        "tags": sorted(edef.tags),
        "count": es.count,
        "available": es.available,
        "affordable": es.affordable,
        "current_cost": _round_cost(cost),
        "effects": effects,
    }
    if edef.max_count is not None:
        result["max_count"] = edef.max_count
    return result


def _tool_purchase(holder: _GameHolder, element_id: str) -> dict[str, Any]:
    edef = holder.definition.get_element(element_id)
    if edef is None:
        return {"error": f"Unknown element: {element_id!r}"}

    state = holder.runtime.get_state()
    es = state.elements[element_id]

    if edef.max_count is not None and es.count >= edef.max_count:
        return {"success": False, "reason": "Already at max count"}
    if not es.available and not es.unlocked:
        return {"success": False, "reason": "Not available (requirements not met)"}

    success = holder.runtime.try_purchase(element_id)
    if success:
        new_state = holder.runtime.get_state()
        return {
            "success": True,
            "element_id": element_id,
            "new_count": new_state.element_count(element_id),
        }
    else:
        return {"success": False, "reason": "Cannot afford"}


def _tool_click(
    holder: _GameHolder, target: str, count: int = 1
) -> dict[str, Any]:
    if count < 1:
        return {"error": "Count must be at least 1"}
    if count > _MAX_CLICKS:
        return {"error": f"Count cannot exceed {_MAX_CLICKS}"}

    ct = holder.definition.get_click_target(target)
    if ct is None:
        return {"error": f"Unknown click target: {target!r}"}

    total = 0.0
    for _ in range(count):
        total += holder.runtime.process_click(target)
    return {
        "target": target,
        "clicks": count,
        "total_earned": round(total, 2),
        "new_balance": round(holder.runtime.get_state().currency_value(target), 2),
    }


def _tool_wait(holder: _GameHolder, seconds: float) -> dict[str, Any]:
    if seconds <= 0:
        return {"error": "Seconds must be positive"}
    if seconds > _MAX_WAIT:
        return {"error": f"Cannot wait more than {_MAX_WAIT} seconds (24h) per call"}

    state = holder.runtime.get_state()
    milestones_before = set(state.milestones_reached.keys())

    # Subdivide into 1-second ticks
    remaining = seconds
    while remaining > 0:
        dt = min(1.0, remaining)
        holder.runtime.tick(dt)
        remaining -= dt

    milestones_after = set(state.milestones_reached.keys())
    new_milestones = sorted(milestones_after - milestones_before)
    holder._milestones_seen.update(new_milestones)

    # Build currency summary
    currencies = {}
    for cdef in holder.definition.currencies:
        cs = state.currencies[cdef.id]
        currencies[cdef.id] = {
            "current": round(cs.current, 2),
            "rate": round(cs.current_rate, 4),
        }

    result: dict[str, Any] = {
        "waited": seconds,
        "time_elapsed": round(state.time_elapsed, 2),
        "currencies": currencies,
    }
    if new_milestones:
        result["new_milestones"] = new_milestones
    return result


def _tool_prestige(holder: _GameHolder, layer_id: str) -> dict[str, Any]:
    layer = holder.definition.get_prestige_layer(layer_id)
    if layer is None:
        return {"error": f"Unknown prestige layer: {layer_id!r}"}

    result = holder.runtime.trigger_prestige(layer_id)
    if result.success:
        return {
            "success": True,
            "reward_amount": round(result.reward_amount, 2),
            "currencies_reset": result.currencies_reset,
            "elements_reset": result.elements_reset,
        }
    else:
        return {"success": False, "reason": result.reason}


def _tool_new_game(holder: _GameHolder) -> dict[str, Any]:
    holder.runtime = GameRuntime(holder.definition)
    holder._milestones_seen = set()
    return {"success": True, "message": "Game reset to initial state"}


# ── Server factory ──────────────────────────────────────────────────


def create_server(definition: GameDefinition) -> FastMCP:
    """Create an MCP server wrapping a GameRuntime for the given definition."""
    holder = _GameHolder(
        definition=definition,
        runtime=GameRuntime(definition),
    )

    mcp = FastMCP(
        name=f"IdleEngine: {definition.config.name}",
    )

    @mcp.tool()
    def get_game_info() -> dict[str, Any]:
        """Get static game overview: currencies, elements, milestones, click targets, prestige layers."""
        return _tool_get_game_info(holder)

    @mcp.tool()
    def get_game_state() -> dict[str, Any]:
        """Get current game state snapshot: currency values/rates, element counts, milestones, time."""
        return _tool_get_game_state(holder)

    @mcp.tool()
    def get_available_purchases() -> dict[str, Any]:
        """Get all currently purchasable elements with cost and time-to-afford."""
        return _tool_get_available_purchases(holder)

    @mcp.tool()
    def get_element_info(element_id: str) -> dict[str, Any]:
        """Get detailed info for a single element: description, costs, effects, category."""
        return _tool_get_element_info(holder, element_id)

    @mcp.tool()
    def purchase(element_id: str) -> dict[str, Any]:
        """Buy an element. Returns success/failure with reason."""
        return _tool_purchase(holder, element_id)

    @mcp.tool()
    def click(target: str, count: int = 1) -> dict[str, Any]:
        """Click a currency target N times (max 1000). Returns total earned."""
        return _tool_click(holder, target, count)

    @mcp.tool()
    def wait(seconds: float) -> dict[str, Any]:
        """Advance game time by the given seconds (max 86400). Time is subdivided into 1s ticks."""
        return _tool_wait(holder, seconds)

    @mcp.tool()
    def prestige(layer_id: str) -> dict[str, Any]:
        """Trigger a prestige reset on the given layer."""
        return _tool_prestige(holder, layer_id)

    @mcp.tool()
    def new_game() -> dict[str, Any]:
        """Reset the game to initial state."""
        return _tool_new_game(holder)

    return mcp
