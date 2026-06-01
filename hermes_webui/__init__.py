"""HermesWebUI — a native Windows desktop shell around the Hermes Agent.

This package is frozen into ``HermesWebUI.exe`` (PyInstaller) and is responsible
for: starting the Hermes dashboard server, serving a small local "shell" web app
(terminal, file drawer, skills, skill-market link) and hosting all of it inside a
native WebView2 window — without the end user having to install Python, Node,
WebView2 or any developer tools.
"""

__version__ = "0.1.0"
