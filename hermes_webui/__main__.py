"""HermesWebUI entrypoint — what ``HermesWebUI.exe`` runs.

Startup sequence:

1. Configure logging under ``%LOCALAPPDATA%\\hermes\\logs\\hermeswebui``.
2. Resolve settings + free ports.
3. Start the Hermes dashboard subprocess and wait until it is healthy.
4. Start our shell FastAPI server (sidebar UI + terminal + files + skills +
   dashboard proxy) on a background thread.
5. Open the native WebView2 window pointed at the shell (or, in ``redirect``
   embed mode, straight at the dashboard).
6. On window close (or if Hermes dies), tear everything down cleanly.

The whole thing is defensive: any fatal startup error is logged and shown to the
user as a tiny HTML error page in the window, with a pointer to the log folder —
because "double-click did nothing" is the worst possible failure for a normal
user to debug.
"""

from __future__ import annotations

import os
import sys
import threading
import time

from . import logging_setup
from .config import load as load_settings
from .logging_setup import get_logger

log = get_logger("hermes_webui.main")


def _run_shell_server(app, settings, ready_evt: threading.Event):
    import uvicorn

    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.shell_port,
        log_level="info",
        access_log=False,
    )
    server = uvicorn.Server(config)

    def _mark_ready():
        # Poll the server's own "started" flag.
        while not server.started:
            time.sleep(0.05)
        ready_evt.set()

    threading.Thread(target=_mark_ready, daemon=True).start()
    server.run()


def _error_window(message: str, log_file) -> None:
    """Show a minimal native window describing a fatal startup error."""
    try:
        import webview

        html = f"""
        <html><body style="font-family:Segoe UI,Arial,sans-serif;background:#11131a;color:#e6e6e6;padding:32px">
        <h2 style="color:#ff7b72">Hermes could not start</h2>
        <p>{message}</p>
        <p>Logs (send these when asking for help):</p>
        <pre style="background:#0b0d12;padding:12px;border-radius:8px">{log_file}</pre>
        </body></html>
        """
        webview.create_window("Hermes — startup error", html=html, width=720, height=420)
        webview.start()
    except Exception:  # noqa: BLE001
        # Last resort: print, so a console build still surfaces the error.
        print(f"Hermes could not start: {message}\nLogs: {log_file}", file=sys.stderr)


def main() -> int:
    log_file = logging_setup.setup()
    log.info("HermesWebUI starting (frozen=%s, pid=%s)", getattr(sys, "frozen", False), os.getpid())

    settings = load_settings()
    log.info(
        "Settings: shell_port=%s dashboard_port=%s embed=%s workspace=%s shell=%s",
        settings.shell_port,
        settings.hermes_dashboard_port,
        settings.embed_mode,
        settings.workspace,
        settings.terminal_shell,
    )

    # 3) Start Hermes dashboard.
    from .hermes_manager import HermesDashboard, HermesNotFoundError

    dashboard = HermesDashboard(settings)
    try:
        dashboard.start()
    except HermesNotFoundError as exc:
        log.error("%s", exc)
        _error_window(str(exc), log_file)
        return 2

    if not dashboard.wait_until_healthy():
        msg = (
            "The Hermes dashboard did not start in time. "
            "See dashboard.log in the logs folder for details."
        )
        _error_window(msg, log_file)
        dashboard.stop()
        return 3

    # 4) Start our shell server.
    from .server import create_app

    app = create_app(settings)
    ready = threading.Event()
    threading.Thread(
        target=_run_shell_server, args=(app, settings, ready), name="shell-server", daemon=True
    ).start()
    if not ready.wait(timeout=20):
        log.error("Shell server failed to start within 20s")
        _error_window("The local UI server failed to start.", log_file)
        dashboard.stop()
        return 4
    log.info("Shell server ready at %s", settings.shell_base_url)

    # If Hermes dies while we're running, close the window so the user notices.
    closing = threading.Event()

    def _on_hermes_exit(_rc):
        if not closing.is_set():
            log.error("Hermes exited; requesting window close.")
            try:
                import webview

                for w in list(webview.windows):
                    w.destroy()
            except Exception:  # noqa: BLE001
                pass

    dashboard.watchdog(_on_hermes_exit)

    # 5) Decide what the window loads.
    if settings.embed_mode == "redirect":
        start_url = settings.dashboard_base_url
    else:
        start_url = settings.shell_base_url + "/"

    def _on_window_closed():
        closing.set()
        log.info("Window closed; shutting down.")
        dashboard.stop()

    # 6) Open the window (blocks on the main thread until closed).
    from .webview_host import run_window

    try:
        run_window(settings, start_url, _on_window_closed)
    finally:
        if not closing.is_set():
            dashboard.stop()

    log.info("HermesWebUI exited cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
