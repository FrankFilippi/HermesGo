"""Locate and manage the Hermes dashboard server subprocess.

The packaged app ships a fully-provisioned Hermes install (repo + venv with the
``[web]`` extra) under ``runtime/hermes``. This module finds it, exports the
environment Hermes expects (``HERMES_HOME``, Git Bash path, portable Node on
PATH), launches ``hermes dashboard --port <p>``, tees its output to a log file,
and waits until the dashboard answers HTTP before we point the window at it.

In a developer checkout where nothing is bundled, it falls back to a ``hermes``
found on PATH so the rest of the shell can still be exercised on any OS.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import httpx

from . import paths
from .config import Settings
from .logging_setup import get_logger

log = get_logger("hermes_webui.manager")


class HermesNotFoundError(RuntimeError):
    pass


def _resolve_launcher() -> tuple[list[str], str]:
    """Return (argv_prefix, description) for invoking Hermes.

    Prefers the bundled venv ``hermes.exe``; then the bundled venv python with
    ``-m hermes``; then a ``hermes`` on PATH (developer fallback).
    """
    exe = paths.bundled_hermes_exe()
    if exe:
        return [str(exe)], f"bundled hermes.exe ({exe})"

    py = paths.bundled_python()
    if py:
        return [str(py), "-m", "hermes"], f"bundled venv python -m hermes ({py})"

    on_path = shutil.which("hermes")
    if on_path:
        return [on_path], f"hermes on PATH ({on_path})"

    raise HermesNotFoundError(
        "Could not locate a Hermes install. Expected a bundled venv under "
        "runtime/hermes (packaged build) or a `hermes` command on PATH (dev)."
    )


def _child_env() -> dict[str, str]:
    """Environment for the Hermes subprocess: home + bundled runtimes on PATH."""
    env = dict(os.environ)
    env["HERMES_HOME"] = str(paths.hermes_home())

    path_parts: list[str] = []
    node_dir = paths.bundled_node_dir()
    if node_dir:
        path_parts.append(str(node_dir))

    git_bash = paths.bundled_git_bash()
    if git_bash:
        # Hermes reads HERMES_GIT_BASH_PATH to run POSIX shell tools on Windows.
        env["HERMES_GIT_BASH_PATH"] = str(git_bash)
        path_parts.append(str(git_bash.parent))

    if path_parts:
        env["PATH"] = os.pathsep.join(path_parts + [env.get("PATH", "")])
    return env


class HermesDashboard:
    """Owns the ``hermes dashboard`` subprocess lifecycle."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.proc: subprocess.Popen | None = None
        self._log_fp = None

    def start(self) -> None:
        argv_prefix, desc = _resolve_launcher()
        argv = argv_prefix + [
            "dashboard",
            "--host",
            self.settings.host,
            "--port",
            str(self.settings.hermes_dashboard_port),
        ]
        log.info("Starting Hermes dashboard via %s", desc)
        log.info("Command: %s", " ".join(argv))

        dash_log = paths.logs_dir() / "dashboard.log"
        self._log_fp = open(dash_log, "a", encoding="utf-8", buffering=1)
        self._log_fp.write(f"\n===== dashboard start {time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")

        creationflags = 0
        if os.name == "nt":
            # Don't pop up a console window for the child on Windows.
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        self.proc = subprocess.Popen(
            argv,
            stdout=self._log_fp,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=_child_env(),
            cwd=str(paths.hermes_home()),
            creationflags=creationflags,
        )
        log.info("Hermes dashboard pid=%s, output -> %s", self.proc.pid, dash_log)

    def wait_until_healthy(self) -> bool:
        """Poll the dashboard URL until it responds or we time out / it dies."""
        deadline = time.monotonic() + self.settings.dashboard_start_timeout
        url = self.settings.dashboard_base_url
        log.info("Waiting up to %ss for dashboard at %s", self.settings.dashboard_start_timeout, url)
        while time.monotonic() < deadline:
            if self.proc and self.proc.poll() is not None:
                log.error("Hermes dashboard exited early with code %s", self.proc.returncode)
                return False
            try:
                r = httpx.get(url, timeout=2.0)
                if r.status_code < 500:
                    log.info("Dashboard is up (HTTP %s)", r.status_code)
                    return True
            except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError):
                pass
            time.sleep(0.5)
        log.error("Timed out waiting for the Hermes dashboard.")
        return False

    def is_running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        if not self.proc:
            return
        log.info("Stopping Hermes dashboard (pid=%s)", self.proc.pid)
        try:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                log.warning("Dashboard did not exit gracefully; killing.")
                self.proc.kill()
        except Exception:  # noqa: BLE001 - shutdown best-effort
            log.exception("Error while stopping the dashboard")
        finally:
            if self._log_fp:
                self._log_fp.close()
                self._log_fp = None

    def watchdog(self, on_exit) -> None:
        """Spawn a thread that calls ``on_exit(returncode)`` if Hermes dies."""

        def _watch():
            if not self.proc:
                return
            rc = self.proc.wait()
            log.error("Hermes dashboard process ended unexpectedly (code %s)", rc)
            on_exit(rc)

        threading.Thread(target=_watch, name="hermes-watchdog", daemon=True).start()
