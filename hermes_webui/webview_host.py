"""Native desktop window via WebView2 (using pywebview's EdgeChromium backend).

Key trick for the "user installs nothing" promise: before any window is created
we point the WebView2 *loader* at our bundled **fixed-version** runtime by setting
``WEBVIEW2_BROWSER_EXECUTABLE_FOLDER``. The loader honours that env var and uses
the exact ``msedgewebview2.exe`` we ship, so the app renders on a clean Windows 10
/ 11 machine that never had the Evergreen WebView2 runtime installed.

If for some reason the fixed runtime isn't bundled, we simply don't set the var
and fall back to whatever Evergreen runtime the OS has (modern Win11 ships one).
"""

from __future__ import annotations

import os

from . import paths
from .config import Settings
from .logging_setup import get_logger

log = get_logger("hermes_webui.webview")


def configure_webview2_runtime() -> None:
    """Wire up the bundled fixed-version WebView2 runtime, if we ship one."""
    folder = paths.webview2_fixed_runtime()
    if folder:
        os.environ["WEBVIEW2_BROWSER_EXECUTABLE_FOLDER"] = str(folder)
        log.info("Using bundled WebView2 fixed runtime: %s", folder)
    else:
        log.info("No bundled WebView2 fixed runtime found; relying on Evergreen runtime.")


def run_window(settings: Settings, start_url: str, on_closed) -> None:
    """Create the native window and block until it is closed.

    ``webview.start()`` must run on the main thread, so this is called from the
    main thread and everything else (servers, watchdog) runs in background threads.
    """
    configure_webview2_runtime()

    import webview  # imported lazily so a dev checkout without pywebview can still import the package

    log.info("Opening window -> %s", start_url)
    window = webview.create_window(
        title="Hermes",
        url=start_url,
        width=settings.window_width,
        height=settings.window_height,
        min_size=(900, 600),
        confirm_close=False,
    )
    window.events.closed += on_closed

    # gui='edgechromium' forces the WebView2 backend on Windows; on other OSes
    # pywebview will pick its native backend (used only for dev preview).
    gui = "edgechromium" if os.name == "nt" else None
    webview.start(gui=gui)
