# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for HermesWebUI.exe (the desktop shell host).
#
# Produces a one-folder build (onedir): HermesWebUI.exe + _internal\. Onedir is
# chosen over onefile because:
#   * the Inno Setup installer copies a folder anyway, so there's no UX win to
#     onefile, and
#   * onefile re-extracts to %TEMP% on every launch (slower start, AV false
#     positives, and a throwaway _MEIPASS that complicates path resolution).
#
# Build is driven by build\build-shell.ps1, which invokes:
#   pyinstaller build\pyinstaller\HermesWebUI.spec --noconfirm --distpath ...

import os
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

repo_root = os.path.abspath(os.path.join(os.getcwd()))

# Bundle our web assets (index.html, app.js, styles.css, vendored xterm) so the
# server can serve them from inside the frozen app.
datas = [
    (os.path.join(repo_root, 'hermes_webui', 'web'), os.path.join('hermes_webui', 'web')),
]

# pywebview + pythonnet (WebView2/EdgeChromium backend) and uvicorn need help.
hiddenimports = []
hiddenimports += collect_submodules('webview')
hiddenimports += collect_submodules('uvicorn')
hiddenimports += [
    'clr',
    'pythonnet',
    'winpty',
    'websockets',
    'websockets.legacy',
    'httpx',
    'anyio',
    'h11',
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan.on',
]

# pywebview ships .NET interop DLLs as data on Windows.
try:
    datas += collect_data_files('webview')
except Exception:
    pass

block_cipher = None

a = Analysis(
    [os.path.join(repo_root, 'hermes_webui', '__main__.py')],
    pathex=[repo_root],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'pytest', 'pandas', 'numpy'],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='HermesWebUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                 # windowed app: no console flash on launch
    icon=os.path.join(repo_root, 'assets', 'hermes.ico')
        if os.path.exists(os.path.join(repo_root, 'assets', 'hermes.ico')) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='HermesWebUI',
)
