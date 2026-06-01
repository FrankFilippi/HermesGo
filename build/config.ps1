# build/config.ps1
# Central configuration for the HermesWebUI Windows build.
# Dot-source this from the other build scripts:  . "$PSScriptRoot\config.ps1"
#
# Bump versions/URLs here in one place. Every URL is pinned to an exact version so
# builds are reproducible and a moved "latest" link can't silently break the build.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# --- Repo / output layout ------------------------------------------------------
$Cfg = [ordered]@{}
$Cfg.RepoRoot      = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Cfg.BuildDir      = $PSScriptRoot
$Cfg.WorkDir       = Join-Path $Cfg.RepoRoot 'build\.work'      # downloads + scratch
$Cfg.StageDir      = Join-Path $Cfg.RepoRoot 'build\.stage'     # assembled payload (-> installer)
$Cfg.DistDir       = Join-Path $Cfg.RepoRoot 'dist'            # finished installer .exe
$Cfg.VendorDir     = Join-Path $Cfg.RepoRoot 'hermes_webui\web\vendor'

# Payload sub-layout under StageDir (mirrors what paths.py expects at runtime):
#   <Stage>\HermesWebUI.exe            (+ _internal\ for onedir PyInstaller)
#   <Stage>\runtime\hermes\            (hermes-agent repo + venv)
#   <Stage>\runtime\node\              (portable Node)
#   <Stage>\runtime\git\               (PortableGit)
#   <Stage>\runtime\webview2\          (WebView2 Fixed Version runtime)
$Cfg.StageRuntime  = Join-Path $Cfg.StageDir 'runtime'

# --- Pinned versions -----------------------------------------------------------
$Cfg.PythonVersion = '3.11.9'      # Hermes requires 3.11
$Cfg.NodeVersion   = '22.11.0'     # Node 22 LTS, matches Hermes installer
$Cfg.GitVersion    = '2.54.0'      # PortableGit, matches Hermes installer
# WebView2 Fixed Version runtime. Microsoft publishes these as a CAB per version.
# Get the current download link + version from:
#   https://developer.microsoft.com/microsoft-edge/webview2/  (Fixed Version)
$Cfg.WebView2Version = '125.0.2535.51'
$Cfg.WebView2Arch    = 'x64'       # x64 | x86 | arm64
$Cfg.XtermVersion       = '5.3.0'
$Cfg.XtermFitVersion    = '0.8.0'

# --- Architecture --------------------------------------------------------------
$Cfg.Arch = 'x64'   # build target; node/git/python/webview2 selected to match

# --- Download URLs (pinned) ----------------------------------------------------
$Cfg.Url = [ordered]@{}
# python.org embeddable build is small and relocatable; we use uv to build the
# Hermes venv (preferred), but keep the embeddable as a documented fallback.
$Cfg.Url.PythonEmbed = "https://www.python.org/ftp/python/$($Cfg.PythonVersion)/python-$($Cfg.PythonVersion)-embed-amd64.zip"
$Cfg.Url.NodeZip     = "https://nodejs.org/dist/v$($Cfg.NodeVersion)/node-v$($Cfg.NodeVersion)-win-x64.zip"
$Cfg.Url.GitPortable = "https://github.com/git-for-windows/git/releases/download/v$($Cfg.GitVersion).windows.1/PortableGit-$($Cfg.GitVersion)-64-bit.7z.exe"
$Cfg.Url.WebView2Cab = "https://msedge.sf.dl.delivery.mp.microsoft.com/filestreamingservice/files/webview2-fixed/$($Cfg.WebView2Version)/Microsoft.WebView2.FixedVersionRuntime.$($Cfg.WebView2Version).$($Cfg.WebView2Arch).cab"
$Cfg.Url.HermesRepo  = 'https://github.com/NousResearch/hermes-agent.git'
$Cfg.Url.HermesInstallPs1 = 'https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.ps1'
$Cfg.Url.XtermJs     = "https://cdn.jsdelivr.net/npm/xterm@$($Cfg.XtermVersion)/lib/xterm.js"
$Cfg.Url.XtermCss    = "https://cdn.jsdelivr.net/npm/xterm@$($Cfg.XtermVersion)/css/xterm.css"
$Cfg.Url.XtermFit    = "https://cdn.jsdelivr.net/npm/xterm-addon-fit@$($Cfg.XtermFitVersion)/lib/xterm-addon-fit.js"

# Read app version from the package.
$Cfg.AppVersion = (Get-Content (Join-Path $Cfg.RepoRoot 'VERSION') -ErrorAction SilentlyContinue | Select-Object -First 1)
if (-not $Cfg.AppVersion) { $Cfg.AppVersion = '0.1.0' }

function Write-Step($msg)  { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Write-Ok($msg)    { Write-Host "    [ok] $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "    [warn] $msg" -ForegroundColor Yellow }

function Invoke-Download($url, $outFile) {
    if (Test-Path $outFile) { Write-Ok "cached: $(Split-Path $outFile -Leaf)"; return }
    New-Item -ItemType Directory -Force -Path (Split-Path $outFile) | Out-Null
    Write-Host "    downloading $url"
    $old = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
    try {
        Invoke-WebRequest -Uri $url -OutFile $outFile -UseBasicParsing
    } finally { $ProgressPreference = $old }
    Write-Ok "saved -> $outFile"
}

# Make $Cfg available to dot-sourcing scripts.
$global:Cfg = $Cfg
