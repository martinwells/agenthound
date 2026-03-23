"""Entry point for the ``agenthound-ui`` console script."""
from __future__ import annotations

import argparse


def main() -> None:
    """Parse arguments and launch the debug UI server."""
    parser = argparse.ArgumentParser(
        prog="agenthound-ui",
        description="Launch the AgentHound debug UI for stepping through recorded fixtures.",
    )
    parser.add_argument(
        "--fixtures-dir",
        default="tests/fixtures",
        help="Path to the fixtures directory (default: tests/fixtures)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=7600,
        help="Port to serve on (default: 7600)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )

    args = parser.parse_args()

    from agenthound.ui.cli import run_ui

    run_ui(
        fixtures_dir=args.fixtures_dir,
        port=args.port,
        host=args.host,
    )


if __name__ == "__main__":
    main()
