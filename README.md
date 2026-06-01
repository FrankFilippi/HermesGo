<div align="center">

# ⬡ HermesGo

### The [Hermes Agent](https://github.com/NousResearch/hermes-agent) as a one-click Windows desktop app

**Download. Double-click. Done.** No Python, no Node.js, no WebView2, no developer tools —
HermesGo bundles everything into a single Windows installer and opens Hermes in a
native desktop window.

[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6?logo=windows&logoColor=white)](#)
[![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)](#)
[![Installer](https://img.shields.io/badge/installer-Inno%20Setup-2E7D32)](#)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Built on Hermes](https://img.shields.io/badge/built%20on-Hermes%20Agent-7c5cff)](https://github.com/NousResearch/hermes-agent)

</div>

---

## ✨ Why HermesGo?

Hermes Agent is brilliant — but getting it running today means a terminal, an install
script, Python 3.11, Node, API setup… fine for developers, a wall for everyone else.

**HermesGo removes the wall.** A normal Windows user installs one `.exe`, double-clicks
**`HermesWebUI.exe`**, and immediately gets a visual Hermes app. Everything the agent
needs is bundled and started automatically.

## 🎯 Features

| | Feature | What you get |
| --- | --- | --- |
| 🪟 | **Native desktop window** | Hermes dashboard & chat in a real WebView2 window — not a browser tab |
| ⌨️ | **Built-in terminal** | A genuine interactive PowerShell / cmd via ConPTY (colors, tab-complete, prompts) |
| 🗂 | **Workspace file drawer** | Browse the current folder and preview files without leaving the app |
| ✦ | **Bundled skills** | Ships with skills pre-installed; view them in one click |
| 🛒 | **Skill Market shortcut** | Jump to [agentskills.io](https://agentskills.io) to add more |
| 🧾 | **Diagnosable by design** | All logs under `%LOCALAPPDATA%\hermes\logs\hermeswebui\` |
| 📦 | **Zero dependencies** | Portable Python 3.11, Node 22, Git, and a **fixed WebView2 runtime** are all bundled |

## 📥 For users — install & run

1. Download the latest **`HermesGo-Setup-x.y.z.exe`** from the
   [Releases](https://github.com/FrankFilippi/HermesGo/releases) page.
2. Run it. It installs **per-user — no administrator rights needed**.
3. Launch **Hermes** from the Start Menu (or desktop shortcut) and you're in.

> First launch starts the local Hermes server automatically and waits for it to be
> ready. If anything goes wrong you get a clear error window pointing at the logs.

## 🛠 For builders — build the installer from source

> Build on **Windows 10/11 (x64)**. PyInstaller, WebView2, `pywinpty`, and Inno Setup
> are Windows-only, so the installer is produced on Windows.

```powershell
git clone git@github.com:FrankFilippi/HermesGo.git
cd HermesGo
pwsh -ExecutionPolicy Bypass -File build\build.ps1
# -> dist\HermesGo-Setup-0.1.0.exe
```

The one command runs four stages: **fetch runtimes → provision Hermes → freeze
`HermesWebUI.exe` → compile the installer**. Full prerequisites and a stage-by-stage
breakdown live in **[docs/BUILD.md](docs/BUILD.md)**; common failures in
**[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**.

<details>
<summary><b>Build flags</b></summary>

| Command | Effect |
| --- | --- |
| `build\build.ps1 -Clean` | wipe scratch + staging, build fresh |
| `build\build.ps1 -SkipFetch` | reuse downloaded runtimes |
| `build\build.ps1 -Stage 3` | run a single stage (1=fetch, 2=hermes, 3=shell, 4=installer) |

</details>

## 🧩 How it works

```
HermesWebUI.exe ──► starts `hermes dashboard`  (127.0.0.1:9119)
                ──► starts shell server (FastAPI, 127.0.0.1:9200)
                        ├─ sidebar UI (Chat / Terminal / Files / Skills / Market)
                        ├─ /ws/terminal  → ConPTY PowerShell
                        ├─ /api/files|skills|...
                        └─ /dashboard/*  → reverse-proxy of the Hermes dashboard
                ──► opens a WebView2 window  → http://127.0.0.1:9200/
                        (WebView2 loader pinned to the bundled FIXED runtime,
                         so it renders on a clean machine with no WebView2)
```

The full picture — topology, design rationale, and the on-disk layout — is in
**[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## ⚙️ Configuration (no rebuild needed)

Override defaults via environment variables (`setx NAME value`, then relaunch):

| Variable | Default | Purpose |
| --- | --- | --- |
| `HERMES_HOME` | `%LOCALAPPDATA%\hermes` | config/data/log home |
| `HERMES_WEBUI_DASHBOARD_PORT` | `9119` | Hermes dashboard port |
| `HERMES_WEBUI_SHELL_PORT` | `9200` | local shell UI port (auto-bumps if busy) |
| `HERMES_WEBUI_EMBED` | `proxy` | `proxy` (sidebar) or `redirect` (dashboard only) |
| `HERMES_WEBUI_WORKSPACE` | launch dir | folder the file drawer / terminal open in |
| `HERMES_WEBUI_SHELL` | `powershell` | `powershell` \| `pwsh` \| `cmd` |

(Full list in [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md#c-runtime-configuration-knobs-no-rebuild-needed).)

## 📁 Project structure

```
HermesGo/
├─ hermes_webui/            # the Python desktop shell (frozen into HermesWebUI.exe)
│  ├─ __main__.py           #   entrypoint — orchestrates startup/shutdown
│  ├─ hermes_manager.py     #   starts & health-checks `hermes dashboard`
│  ├─ server.py             #   FastAPI shell: UI + terminal ws + file/skill APIs
│  ├─ proxy.py              #   reverse-proxies the dashboard under our origin
│  ├─ terminal.py           #   ConPTY (pywinpty) pseudo-console
│  ├─ webview_host.py       #   native WebView2 window (fixed-runtime wiring)
│  ├─ paths.py · config.py · logging_setup.py
│  └─ web/                  #   sidebar UI (index.html, app.js, styles.css, xterm)
├─ build/                   # the Windows build flow
│  ├─ build.ps1             #   one-command orchestrator
│  ├─ fetch-runtimes.ps1    #   stage 1 — portable runtimes + WebView2 fixed runtime
│  ├─ install-hermes.ps1    #   stage 2 — provision Hermes + venv
│  ├─ build-shell.ps1       #   stage 3 — PyInstaller
│  ├─ make-installer.ps1    #   stage 4 — Inno Setup
│  ├─ installer/HermesWebUI.iss
│  └─ pyinstaller/HermesWebUI.spec
├─ docs/                    # BUILD · TROUBLESHOOTING · ARCHITECTURE
├─ assets/                  # icon (hermes.ico)
└─ pyproject.toml · VERSION
```

## 🗺 Roadmap

- [ ] First green build on Windows (see the checklist in [docs/BUILD.md](docs/BUILD.md#5-whats-verified-vs-needs-a-windows-run))
- [ ] Code-signed installer (drop the SmartScreen prompt)
- [ ] Auto-update
- [ ] Custom app icon & installer branding
- [ ] arm64 build

## 🙏 Credits

HermesGo is an independent, community packaging of the open-source
[**Hermes Agent**](https://github.com/NousResearch/hermes-agent) by
[**Nous Research**](https://nousresearch.com). All credit for the agent itself goes
to them. HermesGo only handles the Windows desktop experience and installer.

## 📄 License

[MIT](LICENSE) © Frank Filippi. Hermes Agent and its trademarks belong to Nous Research.
