"""The local "shell" web server.

This FastAPI app is what the WebView2 window actually loads. It renders our chrome
(sidebar: Chat / Terminal / Files / Skills / Skill Market) and exposes the small
APIs those panes need:

* ``GET  /``                      -> the shell SPA (static index.html)
* ``GET  /api/info``              -> ports, workspace, versions, embed mode
* ``GET  /api/files?path=...``    -> workspace file drawer (sandboxed listing)
* ``GET  /api/file?path=...``     -> read a small text file for preview
* ``GET  /api/skills``            -> bundled + user skills under HERMES_HOME/skills
* ``POST /api/open-external``     -> open a URL (e.g. the skill market) in the OS browser
* ``WS   /ws/terminal``           -> interactive PowerShell/cmd via ConPTY
* ``ANY  /dashboard/{path}``      -> reverse-proxied Hermes dashboard (see proxy.py)

Everything binds to 127.0.0.1 only.
"""

from __future__ import annotations

import asyncio
import json
import os
import webbrowser
from pathlib import Path

from fastapi import FastAPI, Query, Request, WebSocket
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, paths
from .config import Settings
from .logging_setup import get_logger
from .proxy import PREFIX as DASHBOARD_PREFIX
from .proxy import DashboardProxy
from .terminal import PtySession

log = get_logger("hermes_webui.server")

# Cap previews / listings so a huge directory or file can't wedge the UI.
MAX_LIST_ENTRIES = 2000
MAX_PREVIEW_BYTES = 256 * 1024


def _safe_join(root: Path, requested: str | None) -> Path:
    """Resolve ``requested`` and ensure it stays within ``root`` (no path escape)."""
    base = root.resolve()
    if not requested:
        return base
    target = (base / requested).resolve() if not os.path.isabs(requested) else Path(requested).resolve()
    # Allow browsing anywhere at/under the workspace root only.
    try:
        target.relative_to(base)
    except ValueError:
        return base
    return target


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="HermesWebUI Shell", docs_url=None, redoc_url=None, openapi_url=None)
    proxy = DashboardProxy(settings)
    workspace_root = Path(settings.workspace)

    @app.on_event("shutdown")
    async def _shutdown():
        await proxy.aclose()

    # --- shell SPA + static assets ----------------------------------------
    web_dir = paths.web_assets_dir()

    @app.get("/", response_class=HTMLResponse)
    async def index():
        index_html = web_dir / "index.html"
        if not index_html.exists():
            return HTMLResponse("<h1>HermesWebUI</h1><p>web assets missing.</p>", status_code=500)
        return FileResponse(index_html)

    # Serve /static/* (app.js, styles.css, vendored xterm) from the web dir.
    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

    # --- small JSON APIs ---------------------------------------------------
    @app.get("/api/info")
    async def info():
        return {
            "version": __version__,
            "embed_mode": settings.embed_mode,
            "workspace": str(workspace_root),
            "skill_market_url": settings.skill_market_url,
            "dashboard_url": settings.dashboard_base_url,
            "dashboard_proxy_path": DASHBOARD_PREFIX + "/",
            "hermes_home": str(paths.hermes_home()),
            "logs_dir": str(paths.logs_dir()),
            "terminal_shell": settings.terminal_shell,
        }

    @app.get("/api/files")
    async def files(path: str | None = Query(default=None)):
        target = _safe_join(workspace_root, path)
        if not target.exists() or not target.is_dir():
            return JSONResponse({"error": "not a directory"}, status_code=404)
        entries = []
        try:
            for i, child in enumerate(sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))):
                if i >= MAX_LIST_ENTRIES:
                    break
                try:
                    stat = child.stat()
                    size = stat.st_size
                    mtime = stat.st_mtime
                except OSError:
                    size, mtime = None, None
                entries.append(
                    {
                        "name": child.name,
                        "is_dir": child.is_dir(),
                        "size": size,
                        "mtime": mtime,
                    }
                )
        except PermissionError:
            return JSONResponse({"error": "permission denied"}, status_code=403)

        rel = ""
        try:
            r = target.resolve().relative_to(workspace_root.resolve())
            rel = "" if str(r) == "." else str(r)
        except ValueError:
            rel = ""
        return {"root": str(workspace_root), "path": rel, "entries": entries}

    @app.get("/api/file")
    async def read_file(path: str = Query(...)):
        target = _safe_join(workspace_root, path)
        if not target.exists() or not target.is_file():
            return JSONResponse({"error": "not a file"}, status_code=404)
        if target.stat().st_size > MAX_PREVIEW_BYTES:
            return JSONResponse({"error": "file too large to preview"}, status_code=413)
        try:
            text = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)
        return {"path": path, "content": text}

    @app.get("/api/skills")
    async def skills():
        skills_root = paths.skills_dir()
        result = []
        if skills_root.exists():
            for child in sorted(skills_root.iterdir()):
                if not child.is_dir():
                    continue
                meta = _read_skill_meta(child)
                result.append(meta)
        return {"skills_dir": str(skills_root), "skills": result}

    @app.post("/api/open-external")
    async def open_external(request: Request):
        data = await request.json()
        url = (data or {}).get("url", "")
        if not (url.startswith("http://") or url.startswith("https://")):
            return JSONResponse({"error": "only http(s) urls allowed"}, status_code=400)
        log.info("Opening external url: %s", url)
        webbrowser.open(url)
        return {"ok": True}

    # --- interactive terminal (ConPTY <-> xterm.js) -----------------------
    @app.websocket("/ws/terminal")
    async def terminal_ws(ws: WebSocket):
        await ws.accept()
        session = PtySession(settings)
        try:
            session.spawn()
        except Exception as exc:  # noqa: BLE001
            log.exception("Failed to spawn terminal")
            await ws.send_text(json.dumps({"type": "error", "message": str(exc)}))
            await ws.close()
            return

        loop = asyncio.get_event_loop()
        stop = asyncio.Event()

        async def pump_out():
            # Read from the pty in a thread (blocking) and forward to the socket.
            while not stop.is_set() and session.is_alive():
                data = await loop.run_in_executor(None, session.read, 65536)
                if data:
                    await ws.send_text(json.dumps({"type": "data", "data": data}))
                else:
                    await asyncio.sleep(0.02)
            stop.set()
            await ws.send_text(json.dumps({"type": "exit"}))

        out_task = asyncio.create_task(pump_out())
        try:
            while not stop.is_set():
                raw = await ws.receive_text()
                msg = json.loads(raw)
                if msg.get("type") == "data":
                    session.write(msg.get("data", ""))
                elif msg.get("type") == "resize":
                    session.resize(int(msg.get("cols", 120)), int(msg.get("rows", 30)))
        except Exception:  # noqa: BLE001 - client disconnect is normal
            pass
        finally:
            stop.set()
            session.close()
            out_task.cancel()

    # --- reverse-proxied Hermes dashboard ---------------------------------
    if settings.embed_mode == "proxy":

        @app.websocket(DASHBOARD_PREFIX + "/{full_path:path}")
        async def dashboard_ws(ws: WebSocket, full_path: str):
            await proxy.handle_ws(ws, full_path)

        @app.api_route(
            DASHBOARD_PREFIX + "/{full_path:path}",
            methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        )
        async def dashboard_http(request: Request, full_path: str):
            return await proxy.handle_http(request, full_path)

        @app.api_route(DASHBOARD_PREFIX, methods=["GET"])
        async def dashboard_root(request: Request):
            return await proxy.handle_http(request, "")

    return app


def _read_skill_meta(skill_dir: Path) -> dict:
    """Best-effort metadata for a skill folder (name, description).

    agentskills.io / Hermes ``SKILL.md`` files carry YAML frontmatter with
    ``name:`` and ``description:`` fields. We parse those first, then fall back
    to the first meaningful body line.
    """
    name = skill_dir.name
    description = ""
    for fname in ("SKILL.md", "skill.md", "README.md"):
        f = skill_dir / fname
        if not f.exists():
            continue
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        front_name, front_desc, body = _parse_frontmatter(head)
        name = front_name or name
        description = front_desc or _first_meaningful_line(body)
        break
    return {"name": name, "description": description, "path": str(skill_dir)}


def _parse_frontmatter(text: str) -> tuple[str, str, str]:
    """Return (name, description, body) from a leading ``---`` YAML block.

    Intentionally a tiny line-based parser (no PyYAML dependency) — it only needs
    flat ``key: value`` pairs, which is all the skill manifests use.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return "", "", text
    name = desc = ""
    end = len(lines)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
        if ":" in lines[i]:
            key, _, val = lines[i].partition(":")
            key, val = key.strip().lower(), val.strip().strip("\"'")
            if key == "name":
                name = val
            elif key == "description":
                desc = val
    body = "\n".join(lines[end + 1 :])
    return name, desc, body


def _first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        line = line.strip().lstrip("#").strip()
        if line and not line.startswith("---"):
            return line[:200]
    return ""
