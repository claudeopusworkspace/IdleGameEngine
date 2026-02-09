from __future__ import annotations

import argparse
import importlib
import sys

from idleengine.definition import GameDefinition
from idleengine.formatting import format_text_report
from idleengine.pacing import PacingBound
from idleengine.simulation import Simulation
from idleengine.strategy import (
    ClickProfile,
    GreedyCheapest,
    GreedyROI,
    SaveForBest,
    Strategy,
)
from idleengine.terminal import Terminal, TerminalCondition


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="idleengine",
        description="IdleEngine — Idle Game Simulation CLI",
    )
    sub = parser.add_subparsers(dest="command")

    sim = sub.add_parser("simulate", help="Run a simulation")
    sim.add_argument("game_module", help="Python module with define_game()")
    sim.add_argument(
        "--strategy",
        default="greedy_cheapest",
        choices=["greedy_cheapest", "greedy_roi", "save_for_best"],
        help="Strategy to use (default: greedy_cheapest)",
    )
    sim.add_argument("--cps", type=float, default=0.0, help="Clicks per second")
    sim.add_argument("--click-target", default=None, help="Currency to click")
    sim.add_argument(
        "--tick-resolution", type=float, default=1.0, help="Seconds per tick"
    )
    sim.add_argument(
        "--mode",
        default="tick",
        choices=["tick", "event_jump"],
        help="Simulation mode",
    )
    sim.add_argument("--seed", type=int, default=None, help="Random seed")
    sim.add_argument(
        "--terminal-time", type=float, default=3600, help="Max simulation time (s)"
    )
    sim.add_argument("--export-csv", default=None, help="CSV export path prefix")
    sim.add_argument("--export-json", default=None, help="JSON export path")
    sim.add_argument("--plot", default=None, help="Plot output path (PNG)")
    sim.add_argument(
        "--monte-carlo",
        type=int,
        default=None,
        help="Number of Monte Carlo runs",
    )

    return parser


def load_game(module_path: str) -> GameDefinition:
    """Import module and call define_game()."""
    mod = importlib.import_module(module_path)
    if not hasattr(mod, "define_game"):
        print(f"Error: module {module_path!r} has no define_game() function")
        sys.exit(1)
    return mod.define_game()


def build_strategy(
    name: str,
    cps: float,
    click_target: str | None,
    definition: GameDefinition,
    runtime=None,
    mode: str = "tick",
) -> Strategy:
    click_profile = None
    active_during_wait = mode == "event_jump"
    if cps > 0 and click_target:
        click_profile = ClickProfile(
            targets={click_target: cps}, active_during_wait=active_during_wait
        )
    elif cps > 0 and definition.click_targets:
        ct = definition.click_targets[0]
        click_profile = ClickProfile(
            targets={ct.currency: cps}, active_during_wait=active_during_wait
        )

    if name == "greedy_cheapest":
        return GreedyCheapest(click_profile=click_profile)
    elif name == "greedy_roi":
        return GreedyROI(runtime=runtime, click_profile=click_profile)
    elif name == "save_for_best":
        return SaveForBest(runtime=runtime, click_profile=click_profile)
    else:
        return GreedyCheapest(click_profile=click_profile)


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "simulate":
        definition = load_game(args.game_module)

        terminal: TerminalCondition = Terminal.time(args.terminal_time)

        strategy = build_strategy(
            args.strategy,
            args.cps,
            args.click_target,
            definition,
            mode=args.mode,
        )

        if args.monte_carlo and args.monte_carlo > 1:
            _run_monte_carlo(definition, strategy, terminal, args)
        else:
            sim = Simulation(
                definition=definition,
                strategy=strategy,
                terminal=terminal,
                tick_resolution=args.tick_resolution,
                seed=args.seed,
                mode=args.mode,
            )

            # For ROI/SaveForBest strategies that need runtime ref
            if hasattr(strategy, "runtime") and strategy.runtime is None:
                strategy.runtime = sim.runtime

            report = sim.run()
            bounds = definition.pacing_bounds if definition.pacing_bounds else None
            print(format_text_report(report, bounds))

            if args.export_csv:
                from idleengine.export import export_csv
                export_csv(report, args.export_csv)
                print(f"\nCSV exported to {args.export_csv}_*.csv")

            if args.export_json:
                from idleengine.export import export_json
                export_json(report, args.export_json)
                print(f"\nJSON exported to {args.export_json}")

            if args.plot:
                from idleengine.visualization import plot_simulation
                plot_simulation(report, args.plot)
                print(f"\nPlot saved to {args.plot}")


def _run_monte_carlo(
    definition: GameDefinition,
    strategy: Strategy,
    terminal: TerminalCondition,
    args,
) -> None:
    """Run multiple simulations and report aggregate results."""
    from idleengine.report import SimulationReport

    n = args.monte_carlo
    milestone_times: dict[str, list[float]] = {}
    total_times: list[float] = []
    stall_count = 0

    for i in range(n):
        sim = Simulation(
            definition=definition,
            strategy=strategy,
            terminal=terminal,
            tick_resolution=args.tick_resolution,
            seed=(args.seed + i) if args.seed is not None else None,
            mode=args.mode,
        )
        if hasattr(strategy, "runtime") and strategy.runtime is None:
            strategy.runtime = sim.runtime

        report = sim.run()
        total_times.append(report.total_time)
        if report.stalls:
            stall_count += 1
        for mid, t in report.milestone_times.items():
            milestone_times.setdefault(mid, []).append(t)

    print(f"Monte Carlo: {n} runs")
    print(f"Total time: mean={sum(total_times)/n:.1f}s, "
          f"min={min(total_times):.1f}s, max={max(total_times):.1f}s")
    print(f"Stall rate: {stall_count}/{n}")
    if milestone_times:
        print("Milestone times (mean / min / max):")
        for mid, times in sorted(milestone_times.items()):
            mean = sum(times) / len(times)
            print(f"  {mid}: {mean:.1f}s / {min(times):.1f}s / {max(times):.1f}s")
