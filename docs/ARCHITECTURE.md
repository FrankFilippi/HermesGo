# Architecture

## Runtime topology

```
                          HermesWebUI.exe  (frozen Python shell, no console)
                          ┌───────────────────────────────────────────────┐
   double-click  ───────► │ __main__.py  (main thread orchestrator)         │
                          │   1. logging  -> %LOCALAPPDATA%\hermes\logs\... │
                          │   2. start Hermes dashboard subprocess          │
                          │   3. start shell FastAPI server (bg thread)     │
                          │   4. open WebView2 window (main thread)         │
                          └───────────────────────────────────────────────┘
                               │                        │
            spawns subprocess  │                        │ serves
                               ▼                        ▼
        ┌──────────────────────────────┐   ┌────────────────────────────────────┐
        │  hermes dashboard             │   │  shell server (FastAPI/uvicorn)      │
        │  127.0.0.1:9119               │   │  127.0.0.1:9200                      │
        │  (bundled venv, [web] extra)  │   │   /                -> sidebar SPA     │
        └──────────────────────────────┘   │   /api/info|files|file|skills        │
                       ▲                    │   /api/open-external                 │
                       │  reverse-proxy     │   /ws/terminal     -> ConPTY shell    │
                       └────────────────────┤   /dashboard/*     -> proxy to :9119  │
                                            └────────────────────────────────────┘
                                                         ▲
                                                         │ loads
                                            ┌────────────────────────────┐
                                            │  WebView2 window            │
                                            │  (bundled FIXED runtime via │
                                            │  WEBVIEW2_BROWSER_EXECUTABLE_│
                                            │  FOLDER) -> http://...:9200/ │
                                            └────────────────────────────┘
```

## Why two servers + a proxy

- **Hermes dashboard (`:9119`)** is upstream's own web app — we don't fork it; we
  run it as-is so the app inherits every Hermes feature and update.
- **Shell server (`:9200`)** is *ours*. It adds the things a desktop app needs that
  the dashboard doesn't provide — an interactive terminal, a file drawer, a skills
  view, and a Skill Market shortcut — and it hosts the sidebar chrome.
- The window loads **our** origin, and the dashboard is **reverse-proxied** under
  `/dashboard/*` so it can be framed inside our chrome (browsers block framing a
  cross-origin app that sends `X-Frame-Options`/CSP `frame-ancestors`; the proxy
  strips those). `HERMES_WEBUI_EMBED=redirect` bypasses the proxy and points the
  window straight at `:9119` — a documented fallback.

## Why these technology choices

| Choice | Reason |
| --- | --- |
| **Pure Python shell** | Hermes is already Python 3.11; reusing it keeps one language and the simplest build chain (vs. .NET/Tauri). |
| **pywebview + WebView2 (EdgeChromium)** | native window with the system-grade Chromium engine; honors a **fixed runtime** so the user installs nothing. |
| **WebView2 *Fixed Version* runtime** | guarantees rendering on a clean Win10/11 box with no Evergreen runtime; pinned + bundled = reproducible. |
| **ConPTY via `pywinpty`** | a *real* interactive terminal (tab-complete, colors, prompts), not a one-shot command runner. |
| **PyInstaller onedir** | a double-clickable `.exe` with no system Python; onedir avoids onefile's per-launch temp extraction. |
| **Inno Setup, per-user** | classic one-click `.exe`, no admin/UAC, Start-Menu + desktop shortcuts. |

## Filesystem at runtime (installed)

```
%LOCALAPPDATA%\Programs\HermesWebUI\        (install dir)
  HermesWebUI.exe
  _internal\                                 (PyInstaller deps + web assets)
  runtime\
    hermes\hermes-agent\                      (Hermes repo)
    hermes\venv\Scripts\{python.exe,hermes.exe}
    node\node.exe
    git\bin\bash.exe
    webview2\<version>\msedgewebview2.exe

%LOCALAPPDATA%\hermes\                        (HERMES_HOME — shared with CLI Hermes)
  logs\hermeswebui\{hermeswebui.log,dashboard.log}
  skills\  sessions\  memories\  cron\
```

Path resolution for all of the above is centralized in `hermes_webui/paths.py`,
which handles three layouts: PyInstaller onedir, PyInstaller onefile, and a plain
source checkout (dev).

## Startup & failure handling

- The dashboard is **health-polled** (HTTP) before the window opens, with a
  configurable timeout; if it dies later a **watchdog** thread closes the window.
- Any fatal startup error renders a small native **error window** pointing at the
  log folder — so "double-click did nothing" always yields a diagnosable message.
- Ports are checked for availability at startup; the shell port auto-bumps if busy.
