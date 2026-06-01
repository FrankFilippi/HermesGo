# Vendored front-end libraries

These files are **fetched at build time** by `build/fetch-runtimes.ps1` and are not
committed (so the repo stays small and license-clean). The build drops the
following here:

| File                    | Source (npm package) | Purpose                         |
| ----------------------- | -------------------- | ------------------------------- |
| `xterm.js`              | `xterm`              | terminal emulator               |
| `xterm.css`             | `xterm`              | terminal styles                 |
| `xterm-addon-fit.js`    | `@xterm/addon-fit`   | auto-resize terminal to its pane |

If you are running the shell from a **source checkout** for development and don't
want to run the full build, fetch them manually:

```powershell
# from repo root
$dst = "hermes_webui/web/vendor"
iwr https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js          -OutFile "$dst/xterm.js"
iwr https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css         -OutFile "$dst/xterm.css"
iwr https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js -OutFile "$dst/xterm-addon-fit.js"
```

```bash
# macOS / Linux dev box
dst=hermes_webui/web/vendor
curl -fsSL https://cdn.jsdelivr.net/npm/xterm@5.3.0/lib/xterm.js -o "$dst/xterm.js"
curl -fsSL https://cdn.jsdelivr.net/npm/xterm@5.3.0/css/xterm.css -o "$dst/xterm.css"
curl -fsSL https://cdn.jsdelivr.net/npm/xterm-addon-fit@0.8.0/lib/xterm-addon-fit.js -o "$dst/xterm-addon-fit.js"
```

> The global `FitAddon.FitAddon` symbol used in `app.js` matches the UMD build of
> `xterm-addon-fit@0.8.x` paired with `xterm@5.3.x`. If you bump to the newer
> `@xterm/*` scoped packages, update the script tags and the global name in
> `app.js` accordingly.
