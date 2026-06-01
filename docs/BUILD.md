# Building the HermesWebUI installer

This builds `dist\HermesGo-Setup-<version>.exe` — the one-click installer you
hand to end users. **Run it on Windows 10 or 11 (x64).** PyInstaller,
pywebview/WebView2, `pywinpty`, and Inno Setup are all Windows-only, so the final
installer cannot be produced on macOS/Linux (you can edit the source there, but
not compile the `.exe`).

---

## 1. Prerequisites (build machine)

Install these once. The commands assume [winget](https://learn.microsoft.com/windows/package-manager/winget/);
`choco` equivalents are noted.

| Tool | Why | Install |
| --- | --- | --- |
| **PowerShell 7+** (`pwsh`) | runs the build scripts | `winget install Microsoft.PowerShell` |
| **Python 3.11** | builds the frozen exe + Hermes venv | `winget install Python.Python.3.11` |
| **uv** (Astral) | fast Python/venv provisioning (auto-installed if missing) | `irm https://astral.sh/uv/install.ps1 \| iex` |
| **Inno Setup 6** | compiles the installer | `winget install JRSoftware.InnoSetup` (or `choco install innosetup`) |
| **Git** | cloning Hermes (PortableGit is also bundled) | `winget install Git.Git` |

> Windows 10/11 ship a Windows-internal `git`/`tar` and `expand.exe`/`cmd` used by
> the scripts. No Visual Studio is required — all Python deps install as wheels.

Recommended OS settings:

- **Enable Win32 long paths** (the Hermes venv + `node_modules` nest deep):
  ```powershell
  # admin PowerShell, once
  New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" `
    -Name LongPathsEnabled -Value 1 -PropertyType DWORD -Force
  ```
- Add an **antivirus exclusion** for the repo's `build\.work` and `build\.stage`
  folders — real-time scanning massively slows PyInstaller and can lock files
  mid-build (see Troubleshooting).

---

## 2. One-command build

```powershell
cd hermes-webui
pwsh -ExecutionPolicy Bypass -File build\build.ps1
```

Output: `dist\HermesGo-Setup-<version>.exe`. First run downloads ~300–600 MB of
runtimes and takes roughly 10–20 minutes depending on network and disk; later runs
reuse the cache under `build\.work` and are much faster.

### Useful flags

| Command | Effect |
| --- | --- |
| `build\build.ps1 -Clean` | wipe `build\.work` + `build\.stage` and build fresh |
| `build\build.ps1 -SkipFetch` | reuse downloaded runtimes, rebuild the rest |
| `build\build.ps1 -Stage 3` | run only one stage (1=fetch, 2=hermes, 3=shell, 4=installer) |

---

## 3. What each stage does

All knobs (versions, URLs, paths) live in **`build\config.ps1`**.

### Stage 1 — `fetch-runtimes.ps1`
Downloads and extracts into `build\.stage\runtime\`:
- **Node.js 22** portable zip → `runtime\node\`
- **PortableGit** (self-extracting 7z) → `runtime\git\`
- **WebView2 Fixed Version runtime** (CAB, expanded with `expand.exe`) → `runtime\webview2\`
- **xterm** + fit addon → `hermes_webui\web\vendor\`

### Stage 2 — `install-hermes.ps1`
- Clones `NousResearch/hermes-agent` → `runtime\hermes\hermes-agent\`
- Builds a **Python 3.11 venv** with the **`[web]`** extra (fastapi + uvicorn) via
  `uv` → `runtime\hermes\venv\` (so `hermes dashboard` works)
- Copies the repo's bundled skills to `runtime\hermes\default-skills\` (the
  installer seeds these into `%LOCALAPPDATA%\hermes\skills`)

### Stage 3 — `build-shell.ps1`
- Creates a throwaway build venv, installs the shell package + `pyinstaller`
- Runs PyInstaller against `build\pyinstaller\HermesWebUI.spec` → **`HermesWebUI.exe`**
  (one-folder build) and copies it to the staging root next to `runtime\`

### Stage 4 — `make-installer.ps1`
- Validates the staged payload is complete
- Runs **Inno Setup** (`ISCC.exe`) against `build\installer\HermesWebUI.iss`
- Emits `dist\HermesGo-Setup-<version>.exe` (per-user install, no admin)

---

## 4. Running from source (developer loop, no installer)

You don't need the full build to iterate on the UI/shell. On a Windows dev box:

```powershell
uv venv --python 3.11 .venv
.\.venv\Scripts\Activate.ps1
uv pip install ".[dev]" fastapi "uvicorn[standard]" httpx websockets pywebview pythonnet pywinpty
# fetch xterm into the vendor folder (see hermes_webui\web\vendor\README.md)
python -m hermes_webui
```

This expects a `hermes` command on PATH (install Hermes normally) since no bundled
venv exists in a source checkout. On **macOS/Linux** the same `python -m hermes_webui`
runs the FastAPI shell with a POSIX-pty terminal fallback and **no** native window
(pywebview/WebView2 are Windows-only here) — useful for hacking on the web UI:
open `http://127.0.0.1:9200/` in a browser. The Chat tab needs a reachable Hermes
dashboard; the Terminal/Files/Skills tabs work standalone.

---

## 5. What's verified vs. needs a Windows run

This project was authored on macOS. Treat the following as **needing a first build
on Windows to confirm**, and check them off as you go:

- [ ] Stage 1 WebView2 CAB link still resolves (Microsoft rotates these — see
      Troubleshooting if it 404s).
- [ ] `uv sync --extra web` / `uv pip install .[web]` succeeds against the current
      Hermes `pyproject` (the `[web]` extra name is upstream's; confirm it exists).
- [ ] PyInstaller bundles pywebview's WebView2 interop DLLs (the spec collects
      `webview` data + hidden imports; verify the window opens).
- [ ] `hermes dashboard --host --port` flags match the installed Hermes version.
- [ ] Inno Setup compiles and the per-user install runs without admin.

If the `hermes dashboard` CLI flags differ in your Hermes version, adjust
`hermes_webui/hermes_manager.py` (the `argv` it builds) — that's the single place
the dashboard is launched.
