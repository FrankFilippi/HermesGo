# Troubleshooting

Two audiences here: **build failures** (you, on the build machine) and **runtime
failures** (an end user who installed the app). The single most useful thing for
runtime issues is the log folder:

```
%LOCALAPPDATA%\hermes\logs\hermeswebui\
    hermeswebui.log     <- the desktop shell (startup, ports, errors)
    dashboard.log       <- captured stdout/stderr of `hermes dashboard`
```

Ask any user reporting a problem to zip and send that folder.

---

## A. Build failures

### A1. WebView2 CAB download 404 / fails (stage 1)
Microsoft rotates the Fixed Version download links and versions.
- Open <https://developer.microsoft.com/microsoft-edge/webview2/> → **Fixed Version**.
- Copy the current version number and the CAB link.
- Update `$Cfg.WebView2Version` (and `$Cfg.Url.WebView2Cab` if the host/path
  changed) in `build\config.ps1`, then re-run `build\build.ps1 -Stage 1`.

### A2. `uv` not found / venv creation fails (stage 2/3)
- Install uv: `irm https://astral.sh/uv/install.ps1 | iex`, then reopen the shell
  (it adds `%USERPROFILE%\.local\bin` to PATH).
- If Python 3.11 itself is missing: `winget install Python.Python.3.11`.

### A3. `[web]` extra install fails (stage 2)
The script falls back automatically (locked → resolve → core + explicit
fastapi/uvicorn). If all fail:
- Check the Hermes `pyproject.toml` for the actual extra name (it may not be
  `web`); set the right one in `install-hermes.ps1`.
- Network/proxy issues: set `HTTPS_PROXY` before building.

### A4. PyInstaller build errors / app exits immediately (stage 3)
- **Missing module at runtime** (e.g. `ModuleNotFoundError: clr` / a uvicorn
  protocol): add it to `hiddenimports` in `build\pyinstaller\HermesWebUI.spec`.
- **pywebview window never opens**: confirm `pythonnet` (`clr`) imported — pywebview's
  EdgeChromium backend needs it. The spec collects `webview` data files; if the
  `.NET` interop DLLs are missing, add them explicitly via `binaries`.
- Build with `console=True` temporarily in the spec to see the traceback, then
  switch back to `console=False`.

### A5. "File in use" / locked files during build
Real-time antivirus scanning PyInstaller's temp output. Add exclusions for
`build\.work` and `build\.stage`, or build with Defender real-time protection
paused.

### A6. Path-too-long errors
Enable Win32 long paths (see BUILD.md §1) and keep the repo near the drive root
(e.g. `C:\src\hermes-webui`).

### A7. Inno Setup `ISCC.exe` not found (stage 4)
`winget install JRSoftware.InnoSetup`. If installed but not found, the script also
checks `%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe`.

---

## B. Runtime failures (end user)

### B1. Double-click does nothing / window flashes and closes
- Open `hermeswebui.log`. The shell shows a small **"Hermes could not start"**
  error window for known failures; if even that doesn't appear, the log has the
  traceback.
- Common cause: the Hermes dashboard didn't become healthy in time — see
  `dashboard.log`.

### B2. "Hermes dashboard did not start in time"
- Look at `dashboard.log`. Typical causes:
  - Missing API keys / first-run setup not done → run the Hermes setup once
    (`hermes setup` from a terminal), or do it from the Chat tab if the dashboard
    loaded far enough.
  - Port `9119` already in use by another app → set `HERMES_WEBUI_DASHBOARD_PORT`
    to a free port (see §C) and relaunch.
- Increase the wait: `setx HERMES_WEBUI_DASHBOARD_TIMEOUT 180` then relaunch.

### B3. Window is blank / white
- Almost always WebView2. The app ships a **fixed runtime**; if the log says
  "relying on Evergreen runtime" the bundled runtime wasn't found — reinstall.
- If the **Chat** tab specifically is blank but Terminal/Files work, the dashboard
  proxy hit something unexpected. Set `HERMES_WEBUI_EMBED=redirect` (see §C) to
  load the dashboard directly as a fallback.

### B4. Terminal says "disconnected" / won't open
- PowerShell not found → the backend falls back to `cmd`. To force cmd:
  `setx HERMES_WEBUI_SHELL cmd`.
- `pywinpty` failed to load (rare, missing VC++ runtime) → check `hermeswebui.log`.

### B5. SmartScreen "Windows protected your PC" on the installer
The installer is unsigned. Click **More info → Run anyway**, or sign it (see §D).

### B6. Files / Skills tabs are empty
- Files: the drawer is sandboxed to the **workspace** (defaults to the folder the
  app launched from / `HERMES_WEBUI_WORKSPACE`). Empty folder = empty list.
- Skills: none installed yet → click **Skill Market** to add some. The skills dir
  is `%LOCALAPPDATA%\hermes\skills`.

---

## C. Runtime configuration knobs (no rebuild needed)

Set as user environment variables (`setx NAME value`, then relaunch):

| Variable | Default | Purpose |
| --- | --- | --- |
| `HERMES_HOME` | `%LOCALAPPDATA%\hermes` | config/data/log home |
| `HERMES_WEBUI_DASHBOARD_PORT` | `9119` | Hermes dashboard port |
| `HERMES_WEBUI_SHELL_PORT` | `9200` | local shell UI port (auto-bumps if busy) |
| `HERMES_WEBUI_DASHBOARD_TIMEOUT` | `90` | seconds to wait for the dashboard |
| `HERMES_WEBUI_EMBED` | `proxy` | `proxy` (sidebar) or `redirect` (dashboard only) |
| `HERMES_WEBUI_WORKSPACE` | launch dir | folder the file drawer/terminal open in |
| `HERMES_WEBUI_SHELL` | `powershell` | `powershell` \| `pwsh` \| `cmd` |
| `HERMES_WEBUI_SKILL_MARKET_URL` | `https://agentskills.io` | Skill Market button target |
| `WEBVIEW2_BROWSER_EXECUTABLE_FOLDER` | bundled | override WebView2 runtime folder |

---

## D. Code signing (optional, removes SmartScreen friction)

The build emits an **unsigned** installer. To sign both the inner `HermesWebUI.exe`
and the installer with an EV/OV cert:

```powershell
# sign the frozen exe before stage 4 (make-installer)
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
    build\.stage\HermesWebUI.exe
# build the installer, then sign it
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 `
    dist\HermesGo-Setup-<version>.exe
```

Inno Setup can also sign automatically via a configured `SignTool` — see the Inno
Setup docs if you want signing folded into stage 4.
