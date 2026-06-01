"""Built-in terminal backend.

A real interactive Windows shell (PowerShell by default, or cmd / pwsh) is spawned
through a pseudo-console (ConPTY) using ``pywinpty``. Bytes flow both ways over a
websocket to an xterm.js terminal in the UI, so the user gets a genuine terminal —
tab completion, colours, interactive prompts — not a fake "run one command" box.

``pywinpty`` is a Windows-only dependency. On any other OS (e.g. the macOS box
this was authored on) we degrade to a POSIX ``pty`` so the terminal pane is still
demonstrable during development.
"""

from __future__ import annotations

import os
import shutil
from typing import Optional

from .config import Settings
from .logging_setup import get_logger

log = get_logger("hermes_webui.terminal")

IS_WINDOWS = os.name == "nt"


def _resolve_shell_argv(settings: Settings) -> list[str]:
    pref = (settings.terminal_shell or "").lower()
    if IS_WINDOWS:
        candidates = {
            "pwsh": ["pwsh.exe", "-NoLogo"],
            "powershell": ["powershell.exe", "-NoLogo"],
            "cmd": ["cmd.exe"],
        }
        argv = candidates.get(pref, candidates["powershell"])
        exe = shutil.which(argv[0])
        if exe:
            return [exe] + argv[1:]
        # Fall back to cmd if the preferred shell isn't found.
        return [shutil.which("cmd.exe") or "cmd.exe"]
    # Developer fallback on macOS/Linux.
    shell = os.environ.get("SHELL", "/bin/bash")
    return [shell]


class PtySession:
    """A single pseudo-console session bound to one websocket."""

    def __init__(self, settings: Settings, cols: int = 120, rows: int = 30):
        self.settings = settings
        self.cols = cols
        self.rows = rows
        self._win_pty = None  # winpty.PTY
        self._win_proc = None
        self._posix_pid: Optional[int] = None
        self._posix_fd: Optional[int] = None

    # --- lifecycle ---------------------------------------------------------
    def spawn(self) -> None:
        argv = _resolve_shell_argv(self.settings)
        cwd = self.settings.workspace if os.path.isdir(self.settings.workspace) else os.getcwd()
        log.info("Spawning terminal %s in %s (%dx%d)", argv, cwd, self.cols, self.rows)
        if IS_WINDOWS:
            self._spawn_windows(argv, cwd)
        else:
            self._spawn_posix(argv, cwd)

    def _spawn_windows(self, argv: list[str], cwd: str) -> None:
        import winpty  # type: ignore

        # winpty.PtyProcess.spawn gives a tidy high-level API over ConPTY.
        cmdline = subprocess_list2cmdline(argv)
        self._win_proc = winpty.PtyProcess.spawn(
            cmdline, dimensions=(self.rows, self.cols), cwd=cwd, env=dict(os.environ)
        )

    def _spawn_posix(self, argv: list[str], cwd: str) -> None:
        import pty

        pid, fd = pty.fork()
        if pid == 0:  # child
            os.chdir(cwd)
            os.execvp(argv[0], argv)
        self._posix_pid, self._posix_fd = pid, fd

    # --- io ----------------------------------------------------------------
    def read(self, size: int = 65536) -> str:
        if IS_WINDOWS:
            try:
                return self._win_proc.read(size)  # returns str
            except EOFError:
                return ""
        assert self._posix_fd is not None
        try:
            return os.read(self._posix_fd, size).decode(errors="replace")
        except OSError:
            return ""

    def write(self, data: str) -> None:
        if IS_WINDOWS:
            self._win_proc.write(data)
        elif self._posix_fd is not None:
            os.write(self._posix_fd, data.encode())

    def resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows
        try:
            if IS_WINDOWS:
                self._win_proc.setwinsize(rows, cols)
            elif self._posix_fd is not None:
                import fcntl
                import struct
                import termios

                fcntl.ioctl(self._posix_fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        except Exception:  # noqa: BLE001
            log.debug("resize failed", exc_info=True)

    def is_alive(self) -> bool:
        if IS_WINDOWS:
            return bool(self._win_proc and self._win_proc.isalive())
        if self._posix_pid is None:
            return False
        try:
            pid, _ = os.waitpid(self._posix_pid, os.WNOHANG)
            return pid == 0
        except ChildProcessError:
            return False

    def close(self) -> None:
        try:
            if IS_WINDOWS and self._win_proc:
                self._win_proc.close(force=True)
            elif self._posix_fd is not None:
                os.close(self._posix_fd)
        except Exception:  # noqa: BLE001
            log.debug("terminal close error", exc_info=True)


def subprocess_list2cmdline(argv: list[str]) -> str:
    """Quote an argv list into a Windows command line."""
    import subprocess

    return subprocess.list2cmdline(argv)
