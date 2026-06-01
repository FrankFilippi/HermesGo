"""Filesystem layout resolution for HermesWebUI.

Two very different layouts exist and this module hides the difference:

* **Installed / packaged** — we run from inside ``HermesWebUI.exe`` produced by
  PyInstaller. ``sys.frozen`` is set and ``sys._MEIPASS`` (onefile) or the exe
  directory (onedir) contains the bundled payload: portable Python/Node, the
  Hermes install, the WebView2 fixed runtime and our web assets.

* **Developer checkout** — we run from a source checkout on any OS (including the
  macOS box this was authored on). Bundled runtimes are absent; we fall back to
  whatever ``hermes`` is on PATH so the shell can still be exercised.

Everything user-facing (config, logs, skills, sessions) lives under
``%LOCALAPPDATA%\\hermes`` on Windows, matching the official Hermes installer so
the desktop app and a CLI ``hermes`` install share one home.
"""

from __future__ import annotations

import os
import sys
from functools import lru_cache
from pathlib import Path


def is_frozen() -> bool:
    """True when running inside the PyInstaller-built ``HermesWebUI.exe``."""
    return bool(getattr(sys, "frozen", False))


@lru_cache(maxsize=1)
def bundle_root() -> Path:
    """Root of the bundled payload that ships next to the executable.

    * onefile PyInstaller: ``sys._MEIPASS`` (the temp extraction dir)
    * onedir PyInstaller:  the directory containing ``HermesWebUI.exe``
    * source checkout:     the repository root (parent of this package)
    """
    if is_frozen():
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass)
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


@lru_cache(maxsize=1)
def install_root() -> Path:
    """Directory the app was installed into (where runtimes sit alongside the exe).

    For onefile builds ``sys._MEIPASS`` is a throwaway temp dir, so the *durable*
    install dir is always the folder holding the executable itself.
    """
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return bundle_root()


def web_assets_dir() -> Path:
    """Static assets (index.html, app.js, styles.css, vendored xterm) directory."""
    return bundle_root() / "hermes_webui" / "web"


def hermes_home() -> Path:
    """The Hermes config/data home.

    Honors ``HERMES_HOME`` (set by the official installer and by our launcher),
    otherwise defaults to ``%LOCALAPPDATA%\\hermes`` on Windows and ``~/.hermes``
    elsewhere — identical to upstream Hermes behaviour.
    """
    env = os.environ.get("HERMES_HOME")
    if env:
        return Path(env)
    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(local) / "hermes"
    return Path.home() / ".hermes"


def logs_dir() -> Path:
    """Where HermesWebUI writes its own logs. Created on demand."""
    d = hermes_home() / "logs" / "hermeswebui"
    d.mkdir(parents=True, exist_ok=True)
    return d


def skills_dir() -> Path:
    """Bundled + user skills directory used by Hermes."""
    return hermes_home() / "skills"


# --- Bundled runtime locations (present only in packaged builds) ---------------

def bundled_python() -> Path | None:
    """Path to the Hermes venv python that ships in the bundle, if present."""
    for candidate in (
        install_root() / "runtime" / "hermes" / "venv" / "Scripts" / "python.exe",
        bundle_root() / "runtime" / "hermes" / "venv" / "Scripts" / "python.exe",
    ):
        if candidate.exists():
            return candidate
    return None


def bundled_hermes_exe() -> Path | None:
    """Path to the bundled ``hermes.exe`` venv wrapper, if present."""
    for candidate in (
        install_root() / "runtime" / "hermes" / "venv" / "Scripts" / "hermes.exe",
        bundle_root() / "runtime" / "hermes" / "venv" / "Scripts" / "hermes.exe",
    ):
        if candidate.exists():
            return candidate
    return None


def bundled_node_dir() -> Path | None:
    """Directory containing the portable Node.js, if present."""
    for candidate in (install_root() / "runtime" / "node", bundle_root() / "runtime" / "node"):
        if (candidate / "node.exe").exists():
            return candidate
    return None


def bundled_git_bash() -> Path | None:
    """Path to bundled Git Bash ``bash.exe`` (Hermes uses it to run shell tools)."""
    for base in (install_root() / "runtime" / "git", bundle_root() / "runtime" / "git"):
        for rel in ("bin/bash.exe", "usr/bin/bash.exe"):
            p = base / rel
            if p.exists():
                return p
    return None


def webview2_fixed_runtime() -> Path | None:
    """Folder of the bundled WebView2 *Fixed Version* runtime, if present.

    When set via ``WEBVIEW2_BROWSER_EXECUTABLE_FOLDER`` the WebView2 loader uses
    this exact runtime instead of any machine-wide Evergreen install, so the app
    works even on a clean Windows box where WebView2 was never installed.
    """
    for base in (install_root() / "runtime" / "webview2", bundle_root() / "runtime" / "webview2"):
        if base.exists():
            # The Microsoft fixed-runtime archive extracts to a single
            # version-named subfolder containing msedgewebview2.exe.
            if (base / "msedgewebview2.exe").exists():
                return base
            for child in base.iterdir():
                if child.is_dir() and (child / "msedgewebview2.exe").exists():
                    return child
    return None
