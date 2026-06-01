# build/make-installer.ps1
# Stage 4: compile the staged payload into a single double-click installer with
# Inno Setup (ISCC.exe), emitting dist\HermesWebUI-Setup-<version>.exe.

param([switch]$Force)

. "$PSScriptRoot\config.ps1"

# --- Sanity: staging payload must be assembled ---------------------------------
Write-Step "Validating staged payload"
$mustExist = @(
    (Join-Path $Cfg.StageDir 'HermesWebUI.exe'),
    (Join-Path $Cfg.StageRuntime 'node\node.exe'),
    (Join-Path $Cfg.StageRuntime 'hermes\venv\Scripts'),
    (Join-Path $Cfg.StageRuntime 'webview2')
)
foreach ($p in $mustExist) {
    if (-not (Test-Path $p)) {
        throw "Staging is incomplete — missing: $p`nRun build.ps1 (or the earlier stages) first."
    }
}
if (-not (Get-ChildItem (Join-Path $Cfg.StageRuntime 'webview2') -Recurse -Filter 'msedgewebview2.exe' -ErrorAction SilentlyContinue)) {
    throw "WebView2 fixed runtime missing under staging. Re-run fetch-runtimes.ps1."
}
Write-Ok "payload looks complete"

# --- Locate ISCC ---------------------------------------------------------------
Write-Step "Locating Inno Setup (ISCC.exe)"
$iscc = Get-Command iscc.exe -ErrorAction SilentlyContinue
if (-not $iscc) {
    foreach ($c in @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
    )) { if (Test-Path $c) { $iscc = @{ Source = $c }; break } }
}
if (-not $iscc) {
    Write-Warn2 "Inno Setup not found. Install it (one of):"
    Write-Warn2 "  winget install JRSoftware.InnoSetup"
    Write-Warn2 "  choco install innosetup"
    throw "ISCC.exe not found on PATH or in Program Files."
}
$isccPath = $iscc.Source
Write-Ok "ISCC: $isccPath"

# --- Compile -------------------------------------------------------------------
Write-Step "Compiling installer"
New-Item -ItemType Directory -Force -Path $Cfg.DistDir | Out-Null
$iss = Join-Path $Cfg.BuildDir 'installer\HermesWebUI.iss'

& $isccPath `
    "/DAppVersion=$($Cfg.AppVersion)" `
    "/DStageDir=$($Cfg.StageDir)" `
    "/DOutputDir=$($Cfg.DistDir)" `
    $iss

$out = Join-Path $Cfg.DistDir "HermesGo-Setup-$($Cfg.AppVersion).exe"
if (-not (Test-Path $out)) { throw "Inno Setup did not produce $out" }

$sizeMB = [math]::Round((Get-Item $out).Length / 1MB, 1)
Write-Ok "installer built -> $out ($sizeMB MB)"
Write-Step "Stage 4 complete. Ship dist\HermesGo-Setup-$($Cfg.AppVersion).exe"
