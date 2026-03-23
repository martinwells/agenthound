"""CLI helper to launch the AgentHound debug UI server."""
from __future__ import annotations

from pathlib import Path


def run_ui(
    fixtures_dir: str = "tests/fixtures",
    port: int = 7600,
    host: str = "127.0.0.1",
) -> None:
    """Configure and start the Uvicorn server for the debug UI.

    Parameters
    ----------
    fixtures_dir:
        Path to the directory containing .json fixture files.
    port:
        Port number to listen on.
    host:
        Host address to bind to.
    """
    import uvicorn

    from agenthound.ui import server
    from agenthound.ui import proxy

    resolved = Path(fixtures_dir).resolve()
    server.fixtures_dir = resolved
    proxy.fixtures_dir = resolved

    uvicorn.run(server.app, host=host, port=port)
