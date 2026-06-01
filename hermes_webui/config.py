"""Runtime configuration for HermesWebUI, resolved from environment variables.

Every value has a sane default so the app "just works" on a double-click, but a
power user (or our troubleshooting docs) can override any of them via env vars
without rebuilding. All knobs are namespaced ``HERMES_WEBUI_*`` except the few
that belong to upstream Hermes (``HERMES_HOME``) or WebView2.
"""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass, field


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _free_port(preferred: int) -> int:
    """Return ``preferred`` if bindable, otherwise an OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]


@dataclass
class Settings:
    # The Hermes dashboard server (`hermes dashboard --port`). 9119 is upstream default.
    hermes_dashboard_port: int = field(default_factory=lambda: _env_int("HERMES_WEBUI_DASHBOARD_PORT", 9119))
    # Our own shell server (sidebar UI, terminal websocket, file/skill APIs, dashboard proxy).
    shell_port: int = field(default_factory=lambda: _env_int("HERMES_WEBUI_SHELL_PORT", 9200))
    host: str = "127.0.0.1"

    # How the Hermes dashboard is shown inside our shell:
    #   "proxy"    — reverse-proxied under our origin so it can be iframed with our
    #                sidebar (terminal/files/skills) around it. Default.
    #   "redirect" — escape hatch: the whole window just loads the dashboard URL
    #                directly (use if the proxy ever misbehaves with a new Hermes).
    embed_mode: str = field(default_factory=lambda: os.environ.get("HERMES_WEBUI_EMBED", "proxy"))

    # Default workspace the file drawer opens on and the terminal starts in.
    workspace: str = field(default_factory=lambda: os.environ.get("HERMES_WEBUI_WORKSPACE", os.getcwd()))

    # "powershell" | "cmd" | "pwsh" — preferred shell for the built-in terminal.
    terminal_shell: str = field(default_factory=lambda: os.environ.get("HERMES_WEBUI_SHELL", "powershell"))

    # External URL for the "Skill Market" button.
    skill_market_url: str = field(
        default_factory=lambda: os.environ.get("HERMES_WEBUI_SKILL_MARKET_URL", "https://agentskills.io")
    )

    # Seconds to wait for the Hermes dashboard to become healthy before giving up.
    dashboard_start_timeout: int = field(default_factory=lambda: _env_int("HERMES_WEBUI_DASHBOARD_TIMEOUT", 90))

    # Window geometry.
    window_width: int = field(default_factory=lambda: _env_int("HERMES_WEBUI_WIN_WIDTH", 1280))
    window_height: int = field(default_factory=lambda: _env_int("HERMES_WEBUI_WIN_HEIGHT", 820))

    def finalize_ports(self) -> "Settings":
        """Resolve port conflicts at startup (another instance, leftover process)."""
        self.shell_port = _free_port(self.shell_port)
        # The dashboard port is passed to `hermes dashboard --port`; if it's busy
        # we let Hermes own a fresh one too and discover it from our manager.
        return self

    @property
    def dashboard_base_url(self) -> str:
        return f"http://{self.host}:{self.hermes_dashboard_port}"

    @property
    def shell_base_url(self) -> str:
        return f"http://{self.host}:{self.shell_port}"


def load() -> Settings:
    return Settings().finalize_ports()
