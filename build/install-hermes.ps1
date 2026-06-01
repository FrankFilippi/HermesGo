# build/install-hermes.ps1
# Stage 2: provision a complete, self-contained Hermes Agent install into the
# staging payload at build\.stage\runtime\hermes, so the installer can ship it
# offline. This clones the repo and builds a Python 3.11 venv (via uv) with the
# `[web]` extra so `hermes dashboard` works out of the box.
#
# We deliberately do NOT pipe the upstream install.ps1 into the bundle, because
# that script installs into %LOCALAPPDATA%\hermes on the *build* machine and edits
# the user PATH. Here we want a *relocatable* copy under our staging dir. We reuse
# the same tools the official installer uses (uv, portable Node) for parity.

param([switch]$Force)

. "$PSScriptRoot\config.ps1"

$hermesStage = Join-Path $Cfg.StageRuntime 'hermes'
$repoDir     = Join-Path $hermesStage 'hermes-agent'
$venvDir     = Join-Path $hermesStage 'venv'

if ($Force -and (Test-Path $hermesStage)) { Remove-Item -Recurse -Force $hermesStage }
New-Item -ItemType Directory -Force -Path $hermesStage | Out-Null

# --- Ensure uv (Astral) is available -------------------------------------------
Write-Step "Ensuring 'uv' is installed (Python provisioning)"
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Write-Host "    installing uv..."
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { throw "uv install failed; install it manually then re-run." }
}
Write-Ok "uv: $($uv.Source)"

# --- Clone Hermes --------------------------------------------------------------
Write-Step "Cloning hermes-agent"
# Prefer the bundled PortableGit so the build doesn't depend on a system git.
$gitExe = Join-Path $Cfg.StageRuntime 'git\cmd\git.exe'
if (-not (Test-Path $gitExe)) { $gitExe = (Get-Command git -ErrorAction Stop).Source }
if (-not (Test-Path $repoDir)) {
    & $gitExe clone --depth 1 $Cfg.Url.HermesRepo $repoDir
    Write-Ok "cloned -> $repoDir"
} else {
    & $gitExe -C $repoDir pull --ff-only
    Write-Ok "updated existing clone"
}

# --- Build the venv with the [web] extra ---------------------------------------
Write-Step "Creating Python $($Cfg.PythonVersion) venv with [web] extra"
& uv venv --python $Cfg.PythonVersion $venvDir
$venvPy = Join-Path $venvDir 'Scripts\python.exe'
if (-not (Test-Path $venvPy)) { throw "venv python not found at $venvPy" }

$env:VIRTUAL_ENV = $venvDir
$env:UV_PROJECT_ENVIRONMENT = $venvDir

Push-Location $repoDir
try {
    # Install the project + web extra. Tiered fallback mirrors the upstream
    # installer: locked install first, then a plain resolve.
    $installed = $false
    if (Test-Path (Join-Path $repoDir 'uv.lock')) {
        try {
            & uv sync --extra web --frozen
            $installed = $true
            Write-Ok "installed from uv.lock (frozen)"
        } catch { Write-Warn2 "frozen uv.lock install failed; falling back to resolve" }
    }
    if (-not $installed) {
        try {
            & uv pip install --python $venvPy ".[web]"
            $installed = $true
            Write-Ok "installed via 'uv pip install .[web]'"
        } catch {
            Write-Warn2 "[web] extra install failed; trying core + explicit web deps"
            & uv pip install --python $venvPy "."
            & uv pip install --python $venvPy fastapi "uvicorn[standard]"
            Write-Ok "installed core + fastapi/uvicorn"
        }
    }
} finally { Pop-Location }

# --- Sanity check: hermes.exe + dashboard command exist ------------------------
Write-Step "Verifying hermes install"
$hermesExe = Join-Path $venvDir 'Scripts\hermes.exe'
if (-not (Test-Path $hermesExe)) {
    Write-Warn2 "hermes.exe wrapper not found; the launcher will fall back to 'python -m hermes'."
} else {
    Write-Ok "hermes.exe -> $hermesExe"
}

# --- Sync bundled skills into the staged HERMES_HOME default skills, if any ----
Write-Step "Staging bundled skills"
$bundledSkillsSrc = Join-Path $repoDir 'skills'
$stageSkills = Join-Path $hermesStage 'default-skills'
if (Test-Path $bundledSkillsSrc) {
    New-Item -ItemType Directory -Force -Path $stageSkills | Out-Null
    Copy-Item -Recurse -Force (Join-Path $bundledSkillsSrc '*') $stageSkills
    Write-Ok "copied bundled skills -> $stageSkills (installer seeds these into %LOCALAPPDATA%\hermes\skills)"
} else {
    Write-Warn2 "no bundled skills directory in the repo; skipping (Skill Market still available)."
}

Write-Step "Stage 2 complete: Hermes provisioned at $hermesStage"
