"""FastAPI server for the AgentHound debug UI."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AgentHound Debug UI", version="0.1.0")

# CORS for localhost frontend dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:7600",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:7600",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module-level variable set by cli.py before the server starts.
fixtures_dir: Path = Path("tests/fixtures")

# ── Proxy router ─────────────────────────────────────────────────────────
from agenthound.ui.proxy import router as proxy_router, flush as proxy_flush  # noqa: E402

app.include_router(proxy_router)


@app.on_event("shutdown")
async def _shutdown_proxy():
    """Flush any pending proxy session on server shutdown."""
    proxy_flush()

# Directory for pre-built frontend static assets.
_STATIC_DIR = Path(__file__).parent / "static"


def _read_fixture(path: Path) -> Dict[str, Any]:
    """Read and parse a fixture JSON file."""
    text = path.read_text(encoding="utf-8")
    return json.loads(text)


def _fixture_summary(name: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract summary fields from parsed fixture data."""
    llm_calls = data.get("llm_calls", [])
    total_input = 0
    total_output = 0
    for call in llm_calls:
        usage = call.get("usage") or {}
        total_input += usage.get("input_tokens", 0)
        total_output += usage.get("output_tokens", 0)
    return {
        "name": name,
        "path": f"fixtures/{name}",
        "recorded_at": data.get("recorded_at"),
        "tags": data.get("tags", []),
        "num_exchanges": len(data.get("exchanges", [])),
        "num_llm_calls": len(llm_calls),
        "input_tokens": total_input,
        "output_tokens": total_output,
    }


@app.get("/api/fixtures")
async def list_fixtures() -> List[Dict[str, Any]]:
    """List all .json fixture files with summary info."""
    if not fixtures_dir.is_dir():
        return []

    results: List[Dict[str, Any]] = []
    for path in sorted(fixtures_dir.glob("*.json")):
        try:
            data = _read_fixture(path)
            results.append(_fixture_summary(path.name, data))
        except (json.JSONDecodeError, OSError):
            # Skip files that can't be read or parsed.
            continue
    return results


@app.get("/api/fixtures/{name}")
async def get_fixture(name: str) -> JSONResponse:
    """Return the full fixture JSON for a specific file."""
    path = fixtures_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Fixture not found: {name}")

    try:
        data = _read_fixture(path)
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Error reading fixture: {exc}")

    return JSONResponse(content=data)


def _build_steps(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build a step-by-step timeline from fixture llm_calls."""
    llm_calls = data.get("llm_calls", [])
    steps: List[Dict[str, Any]] = []
    cumulative_tokens = 0
    all_tools: List[str] = []
    total_duration_ms = 0.0
    model: Optional[str] = None

    for i, call in enumerate(llm_calls):
        usage = call.get("usage") or {}
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        duration_ms = call.get("duration_ms", 0.0)

        cumulative_tokens += input_tokens + output_tokens
        total_duration_ms += duration_ms

        call_model = call.get("model", "")
        if model is None and call_model:
            model = call_model

        tool_calls = call.get("tool_calls", [])
        tool_calls_out = []
        for tc in tool_calls:
            tool_name = tc.get("tool_name", "")
            tool_calls_out.append({
                "tool_name": tool_name,
                "arguments": tc.get("arguments", {}),
            })
            if tool_name and tool_name not in all_tools:
                all_tools.append(tool_name)

        steps.append({
            "index": i,
            "type": "llm_call",
            "model": call_model,
            "provider": call.get("provider", ""),
            "duration_ms": duration_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "tool_calls": tool_calls_out,
            "response_text": call.get("response_text", ""),
            "error": call.get("error"),
            "messages_in": call.get("messages_in", []),
            "cumulative_tokens": cumulative_tokens,
        })

    summary = {
        "total_steps": len(steps),
        "total_tokens": cumulative_tokens,
        "total_duration_ms": total_duration_ms,
        "tools_used": all_tools,
        "model": model or "",
        "tags": data.get("tags", []),
    }

    return {"steps": steps, "summary": summary}


@app.get("/api/fixtures/{name}/steps")
async def get_fixture_steps(name: str) -> JSONResponse:
    """Return the step-by-step timeline for the debugger."""
    path = fixtures_dir / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Fixture not found: {name}")

    try:
        data = _read_fixture(path)
    except (json.JSONDecodeError, OSError) as exc:
        raise HTTPException(status_code=500, detail=f"Error reading fixture: {exc}")

    return JSONResponse(content=_build_steps(data))


# ── Live updates (SSE) ──────────────────────────────────────────────────

@app.get("/api/live")
async def live_updates():
    """SSE stream that pushes fixture updates when files appear or change."""

    async def event_stream():
        # Seed with current files so we don't emit events for every existing
        # fixture on initial connect — only truly new/modified files trigger.
        known_files: Dict[str, float] = {}
        if fixtures_dir.is_dir():
            for path in fixtures_dir.glob("*.json"):
                try:
                    known_files[path.name] = path.stat().st_mtime
                except OSError:
                    continue
        while True:
            current_files: Dict[str, float] = {}
            if fixtures_dir.is_dir():
                for path in fixtures_dir.glob("*.json"):
                    try:
                        current_files[path.name] = path.stat().st_mtime
                    except OSError:
                        continue

            # Detect new or modified files
            for name, mtime in current_files.items():
                if name not in known_files or known_files[name] < mtime:
                    try:
                        data = _read_fixture(fixtures_dir / name)
                        summary = _fixture_summary(name, data)
                        event_type = "new" if name not in known_files else "modified"
                        payload = {"type": event_type, "name": name, "summary": summary}
                        yield f"event: fixture_update\ndata: {json.dumps(payload)}\n\n"
                    except (json.JSONDecodeError, OSError):
                        pass

            known_files = dict(current_files)
            yield ": heartbeat\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# Cached stats to avoid re-parsing all fixtures on every poll
_stats_cache: Dict[str, Any] = {}
_stats_cache_files: Dict[str, float] = {}  # {filename: mtime} at last computation


@app.get("/api/stats")
async def get_stats() -> JSONResponse:
    """Return aggregate stats across all fixtures.

    Uses a cache keyed on file mtimes to avoid re-parsing unchanged files.
    """
    global _stats_cache, _stats_cache_files

    # Check if anything changed
    current_files: Dict[str, float] = {}
    if fixtures_dir.is_dir():
        for path in fixtures_dir.glob("*.json"):
            try:
                current_files[path.name] = path.stat().st_mtime
            except OSError:
                continue

    if current_files == _stats_cache_files and _stats_cache:
        return JSONResponse(content=_stats_cache)

    # Recompute
    total_fixtures = 0
    total_llm_calls = 0
    total_input_tokens = 0
    total_output_tokens = 0
    latest_fixture: Optional[str] = None
    latest_mtime = 0.0
    model_counts: Dict[str, int] = {}
    tag_counts: Dict[str, int] = {}
    provider_counts: Dict[str, int] = {}
    # Per-session data for graphs
    sessions: List[Dict[str, Any]] = []

    for name, mtime in current_files.items():
        try:
            data = _read_fixture(fixtures_dir / name)
            total_fixtures += 1
            llm_calls = data.get("llm_calls", [])
            total_llm_calls += len(llm_calls)
            sess_input = 0
            sess_output = 0
            for call in llm_calls:
                usage = call.get("usage") or {}
                inp = usage.get("input_tokens", 0)
                outp = usage.get("output_tokens", 0)
                total_input_tokens += inp
                total_output_tokens += outp
                sess_input += inp
                sess_output += outp
                m = call.get("model", "")
                if m:
                    model_counts[m] = model_counts.get(m, 0) + 1
                p = call.get("provider", "")
                if p:
                    provider_counts[p] = provider_counts.get(p, 0) + 1
            for tag in data.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest_fixture = name
            sessions.append({
                "name": name,
                "recorded_at": data.get("recorded_at"),
                "num_calls": len(llm_calls),
                "input_tokens": sess_input,
                "output_tokens": sess_output,
                "duration_ms": data.get("total_duration_ms", 0.0),
            })
        except (json.JSONDecodeError, OSError):
            continue

    # Sort sessions by recorded_at
    sessions.sort(key=lambda s: s.get("recorded_at") or "")

    _stats_cache = {
        "total_fixtures": total_fixtures,
        "total_llm_calls": total_llm_calls,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "latest_fixture": latest_fixture,
        "models": model_counts,
        "tags": tag_counts,
        "providers": provider_counts,
        "sessions": sessions,
    }
    _stats_cache_files = current_files

    return JSONResponse(content=_stats_cache)


# ── Static file serving / SPA catch-all ─────────────────────────────────

def _mount_static() -> None:
    """Mount the static directory if it exists (built frontend assets)."""
    if _STATIC_DIR.is_dir():
        app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


_mount_static()


@app.get("/{full_path:path}")
async def spa_catchall(request: Request, full_path: str) -> FileResponse:
    """Serve index.html for any non-API path (SPA routing)."""
    # Try to serve a real file first (e.g. favicon.ico, assets)
    file_path = _STATIC_DIR / full_path
    if full_path and file_path.is_file():
        return FileResponse(str(file_path))

    # Fall back to index.html for client-side routing
    index = _STATIC_DIR / "index.html"
    if index.is_file():
        return FileResponse(str(index))

    raise HTTPException(
        status_code=404,
        detail="Frontend not built. Run the frontend build first, or access /api/ endpoints directly.",
    )
