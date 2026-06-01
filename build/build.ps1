# build/build.ps1
# One-command build for the HermesWebUI Windows installer.
#
#   pwsh -ExecutionPolicy Bypass -File build\build.ps1
#
# Runs all four stages in order:
#   1. fetch-runtimes  — portable Node, PortableGit, WebView2 fixed runtime, xterm
#   2. install-hermes  — clone Hermes + build the Python venv with [web]
#   3. build-shell     — PyInstaller -> HermesWebUI.exe, staged with the runtimes
#   4. make-installer  — Inno Setup -> dist\HermesWebUI-Setup-<ver>.exe
#
# Flags:
#   -Clean       wipe build\.work and build\.stage first (fresh build)
#   -SkipFetch   skip stage 1 (reuse already-downloaded runtimes)
#   -Stage <n>   run a single stage only (1..4) — handy when iterating
#
# See docs\BUILD.md for prerequisites and docs\TROUBLESHOOTING.md for failures.

[CmdletBinding()]
param(
    [switch]$Clean,
    [switch]$SkipFetch,
    [ValidateRange(1,4)][int]$Stage = 0
)

. "$PSScriptRoot\config.ps1"

$sw = [System.Diagnostics.Stopwatch]::StartNew()

Write-Host "HermesWebUI build  (app v$($Cfg.AppVersion))" -ForegroundColor Magenta
Write-Host "Repo:  $($Cfg.RepoRoot)"
Write-Host "Stage: $($Cfg.StageDir)"
Write-Host "Dist:  $($Cfg.DistDir)"

if ($Clean) {
    Write-Step "Cleaning previous build artifacts"
    foreach ($p in @($Cfg.WorkDir, $Cfg.StageDir)) {
        if (Test-Path $p) { Remove-Item -Recurse -Force $p; Write-Ok "removed $p" }
    }
}

function Invoke-Stage($n) {
    switch ($n) {
        1 { & "$PSScriptRoot\fetch-runtimes.ps1" }
        2 { & "$PSScriptRoot\install-hermes.ps1" }
        3 { & "$PSScriptRoot\build-shell.ps1" }
        4 { & "$PSScriptRoot\make-installer.ps1" }
    }
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Stage $n failed (exit $LASTEXITCODE)." }
}

try {
    if ($Stage -ne 0) {
        Invoke-Stage $Stage
    } else {
        if (-not $SkipFetch) { Invoke-Stage 1 } else { Write-Warn2 "skipping fetch (stage 1)" }
        Invoke-Stage 2
        Invoke-Stage 3
        Invoke-Stage 4
    }
    $sw.Stop()
    Write-Host "`nBUILD SUCCEEDED in $([math]::Round($sw.Elapsed.TotalMinutes,1)) min" -ForegroundColor Green
    if ($Stage -eq 0 -or $Stage -eq 4) {
        Write-Host "Installer: $(Join-Path $Cfg.DistDir ("HermesGo-Setup-{0}.exe" -f $Cfg.AppVersion))" -ForegroundColor Green
    }
} catch {
    $sw.Stop()
    Write-Host "`nBUILD FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "See docs\TROUBLESHOOTING.md for common failures." -ForegroundColor Yellow
    exit 1
}
