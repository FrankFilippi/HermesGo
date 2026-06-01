# build/fetch-runtimes.ps1
# Stage 1: download + extract every portable runtime the installer will bundle,
# so the finished app needs NOTHING from the end user's machine: portable Node,
# PortableGit, the WebView2 Fixed Version runtime, and the vendored xterm assets.
#
# Idempotent: re-running reuses anything already downloaded under build\.work.

param([switch]$Force)

. "$PSScriptRoot\config.ps1"

if ($Force -and (Test-Path $Cfg.WorkDir)) { Remove-Item -Recurse -Force $Cfg.WorkDir }
New-Item -ItemType Directory -Force -Path $Cfg.WorkDir, $Cfg.StageRuntime | Out-Null

# --- Node.js (portable zip) ----------------------------------------------------
Write-Step "Node.js $($Cfg.NodeVersion) (portable)"
$nodeZip = Join-Path $Cfg.WorkDir 'node.zip'
Invoke-Download $Cfg.Url.NodeZip $nodeZip
$nodeStage = Join-Path $Cfg.StageRuntime 'node'
if (-not (Test-Path (Join-Path $nodeStage 'node.exe'))) {
    $tmp = Join-Path $Cfg.WorkDir 'node-extract'
    if (Test-Path $tmp) { Remove-Item -Recurse -Force $tmp }
    Expand-Archive -Path $nodeZip -DestinationPath $tmp -Force
    # zip extracts to node-vX.Y.Z-win-x64\ ; flatten that into runtime\node
    $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
    if (Test-Path $nodeStage) { Remove-Item -Recurse -Force $nodeStage }
    Move-Item $inner.FullName $nodeStage
    Write-Ok "Node staged -> $nodeStage"
} else { Write-Ok "Node already staged" }

# --- PortableGit (self-extracting 7z) -----------------------------------------
Write-Step "PortableGit $($Cfg.GitVersion)"
$gitExe = Join-Path $Cfg.WorkDir 'PortableGit.7z.exe'
Invoke-Download $Cfg.Url.GitPortable $gitExe
$gitStage = Join-Path $Cfg.StageRuntime 'git'
if (-not (Test-Path (Join-Path $gitStage 'bin\bash.exe'))) {
    if (Test-Path $gitStage) { Remove-Item -Recurse -Force $gitStage }
    New-Item -ItemType Directory -Force -Path $gitStage | Out-Null
    # The self-extractor supports silent extraction to a target dir.
    Write-Host "    extracting PortableGit..."
    & $gitExe -o"$gitStage" -y | Out-Null
    if (-not (Test-Path (Join-Path $gitStage 'bin\bash.exe'))) {
        throw "PortableGit extraction did not produce bin\bash.exe under $gitStage"
    }
    Write-Ok "Git staged -> $gitStage"
} else { Write-Ok "Git already staged" }

# --- WebView2 Fixed Version runtime (CAB) -------------------------------------
Write-Step "WebView2 Fixed Runtime $($Cfg.WebView2Version) ($($Cfg.WebView2Arch))"
$wv2Cab = Join-Path $Cfg.WorkDir 'webview2.cab'
try {
    Invoke-Download $Cfg.Url.WebView2Cab $wv2Cab
} catch {
    Write-Warn2 "Could not download WebView2 CAB from the pinned URL."
    Write-Warn2 "Microsoft rotates these links. Get the current Fixed Version link from:"
    Write-Warn2 "  https://developer.microsoft.com/microsoft-edge/webview2/  (Fixed Version section)"
    Write-Warn2 "Update `$Cfg.Url.WebView2Cab / WebView2Version in build\config.ps1 and re-run."
    throw
}
$wv2Stage = Join-Path $Cfg.StageRuntime 'webview2'
if (-not (Get-ChildItem $wv2Stage -Recurse -Filter 'msedgewebview2.exe' -ErrorAction SilentlyContinue)) {
    if (Test-Path $wv2Stage) { Remove-Item -Recurse -Force $wv2Stage }
    New-Item -ItemType Directory -Force -Path $wv2Stage | Out-Null
    Write-Host "    expanding CAB..."
    & expand.exe $wv2Cab -F:* $wv2Stage | Out-Null
    $found = Get-ChildItem $wv2Stage -Recurse -Filter 'msedgewebview2.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $found) { throw "WebView2 CAB did not expand to a msedgewebview2.exe under $wv2Stage" }
    Write-Ok "WebView2 staged -> $($found.Directory.FullName)"
} else { Write-Ok "WebView2 already staged" }

# --- Vendored front-end (xterm) -----------------------------------------------
Write-Step "Front-end vendor assets (xterm $($Cfg.XtermVersion))"
New-Item -ItemType Directory -Force -Path $Cfg.VendorDir | Out-Null
Invoke-Download $Cfg.Url.XtermJs  (Join-Path $Cfg.VendorDir 'xterm.js')
Invoke-Download $Cfg.Url.XtermCss (Join-Path $Cfg.VendorDir 'xterm.css')
Invoke-Download $Cfg.Url.XtermFit (Join-Path $Cfg.VendorDir 'xterm-addon-fit.js')
Write-Ok "vendor assets staged -> $($Cfg.VendorDir)"

Write-Step "Stage 1 complete: runtimes fetched."
