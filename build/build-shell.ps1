# build/build-shell.ps1
# Stage 3: freeze the Python desktop shell into HermesWebUI.exe with PyInstaller
# and copy it into the staging payload alongside the runtimes.
#
# Uses its OWN throwaway build venv (not the Hermes venv) so the shell's deps and
# Hermes's deps never collide.

param([switch]$Force)

. "$PSScriptRoot\config.ps1"

$buildVenv = Join-Path $Cfg.WorkDir 'build-venv'
$distOut   = Join-Path $Cfg.WorkDir 'pyinstaller-dist'
$workOut   = Join-Path $Cfg.WorkDir 'pyinstaller-build'

if ($Force) {
    foreach ($p in @($buildVenv, $distOut, $workOut)) { if (Test-Path $p) { Remove-Item -Recurse -Force $p } }
}

# --- Verify vendored xterm is present (fetch-runtimes must have run) -----------
Write-Step "Checking front-end vendor assets"
foreach ($f in @('xterm.js','xterm.css','xterm-addon-fit.js')) {
    if (-not (Test-Path (Join-Path $Cfg.VendorDir $f))) {
        throw "Missing $f in $($Cfg.VendorDir). Run build\fetch-runtimes.ps1 first."
    }
}
Write-Ok "vendor assets present"

# --- Build venv + deps ---------------------------------------------------------
Write-Step "Creating build venv ($($Cfg.PythonVersion))"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if ($uv) {
    & uv venv --python $Cfg.PythonVersion $buildVenv
} else {
    & py -3.11 -m venv $buildVenv
}
$py = Join-Path $buildVenv 'Scripts\python.exe'
if (-not (Test-Path $py)) { throw "build venv python missing at $py" }

Write-Step "Installing shell + build dependencies"
& $py -m pip install --upgrade pip
# Install the shell package (pulls fastapi/uvicorn/httpx/websockets/pywebview/
# pythonnet/pywinpty per pyproject) plus the [build] extra (pyinstaller).
Push-Location $Cfg.RepoRoot
try {
    & $py -m pip install ".[build]"
} finally { Pop-Location }
Write-Ok "deps installed"

# --- Run PyInstaller -----------------------------------------------------------
Write-Step "Freezing HermesWebUI.exe (PyInstaller)"
Push-Location $Cfg.RepoRoot   # spec resolves repo_root from CWD
try {
    & $py -m PyInstaller "build\pyinstaller\HermesWebUI.spec" `
        --noconfirm `
        --distpath $distOut `
        --workpath $workOut
} finally { Pop-Location }

$frozenDir = Join-Path $distOut 'HermesWebUI'
$frozenExe = Join-Path $frozenDir 'HermesWebUI.exe'
if (-not (Test-Path $frozenExe)) { throw "PyInstaller did not produce $frozenExe" }
Write-Ok "built -> $frozenExe"

# --- Copy frozen app into the staging payload root -----------------------------
Write-Step "Staging the frozen shell"
# Layout: <stage>\HermesWebUI.exe + <stage>\_internal\...  ;  runtimes live in <stage>\runtime
Get-ChildItem $frozenDir -Force | ForEach-Object {
    Copy-Item $_.FullName -Destination $Cfg.StageDir -Recurse -Force
}
Write-Ok "shell staged -> $($Cfg.StageDir)"

Write-Step "Stage 3 complete: HermesWebUI.exe frozen and staged."
