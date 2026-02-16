"""CLI entry point: python -m idleengine.mcp <game_module>"""

from __future__ import annotations

import sys


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python -m idleengine.mcp <game_module>", file=sys.stderr)
        print("Example: python -m idleengine.mcp examples.cookie_example", file=sys.stderr)
        sys.exit(1)

    module_path = sys.argv[1]

    # Redirect stdout to stderr during module loading in case define_game() prints
    real_stdout = sys.stdout
    sys.stdout = sys.stderr
    try:
        from idleengine.cli import load_game

        definition = load_game(module_path)
    finally:
        sys.stdout = real_stdout

    from idleengine.mcp.server import create_server

    server = create_server(definition)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
