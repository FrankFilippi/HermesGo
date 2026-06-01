"""Reverse-proxy the Hermes dashboard under our own origin.

Why proxy instead of pointing an iframe straight at ``http://127.0.0.1:9119``?
Browser engines (WebView2 included) refuse to frame a response that sends
``X-Frame-Options: DENY`` or a restrictive ``Content-Security-Policy:
frame-ancestors``. Rather than depend on how a given Hermes version configures
those headers, we proxy the dashboard through ``/dashboard/`` on our shell server
and strip the framing-related headers, so it always renders inside our chrome and
is same-origin with our terminal/file/skill panes.

Set ``HERMES_WEBUI_EMBED=redirect`` to bypass this entirely (the window then loads
the dashboard URL directly) — a documented escape hatch if a future Hermes does
something the proxy doesn't expect.

This proxies HTTP (including streamed SSE) and WebSocket traffic. It is a thin,
header-rewriting passthrough — not a general-purpose proxy — but covers what the
dashboard needs.
"""

from __future__ import annotations

import httpx
from fastapi import Request, WebSocket
from fastapi.responses import Response, StreamingResponse
from starlette.websockets import WebSocketDisconnect

from .config import Settings
from .logging_setup import get_logger

log = get_logger("hermes_webui.proxy")

# Hop-by-hop headers that must not be forwarded (RFC 7230) + framing headers we strip.
_STRIP_RESPONSE_HEADERS = {
    "content-encoding",
    "content-length",
    "transfer-encoding",
    "connection",
    "keep-alive",
    "x-frame-options",
    "content-security-policy",
    "content-security-policy-report-only",
}
_STRIP_REQUEST_HEADERS = {"host", "connection", "keep-alive", "transfer-encoding"}

PREFIX = "/dashboard"


class DashboardProxy:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = httpx.AsyncClient(base_url=settings.dashboard_base_url, timeout=None)

    async def aclose(self) -> None:
        await self._client.aclose()

    def _target_path(self, full_path: str) -> str:
        # full_path is whatever followed /dashboard
        return "/" + full_path.lstrip("/")

    async def handle_http(self, request: Request, full_path: str) -> Response:
        url = self._target_path(full_path)
        headers = {k: v for k, v in request.headers.items() if k.lower() not in _STRIP_REQUEST_HEADERS}
        body = await request.body()

        req = self._client.build_request(
            request.method,
            url,
            headers=headers,
            params=request.query_params,
            content=body if body else None,
        )
        try:
            upstream = await self._client.send(req, stream=True)
        except httpx.ConnectError:
            return Response("Hermes dashboard is not reachable.", status_code=502)

        resp_headers = {
            k: v for k, v in upstream.headers.items() if k.lower() not in _STRIP_RESPONSE_HEADERS
        }
        media_type = upstream.headers.get("content-type")

        async def _stream():
            try:
                async for chunk in upstream.aiter_raw():
                    yield chunk
            finally:
                await upstream.aclose()

        return StreamingResponse(
            _stream(),
            status_code=upstream.status_code,
            headers=resp_headers,
            media_type=media_type,
        )

    async def handle_ws(self, client_ws: WebSocket, full_path: str) -> None:
        import websockets

        await client_ws.accept()
        target = self.settings.dashboard_base_url.replace("http://", "ws://") + self._target_path(full_path)
        try:
            async with websockets.connect(target, open_timeout=10) as upstream:
                await _pump_websocket(client_ws, upstream)
        except Exception as exc:  # noqa: BLE001
            log.warning("dashboard ws proxy error for %s: %s", target, exc)
            try:
                await client_ws.close()
            except Exception:  # noqa: BLE001
                pass


async def _pump_websocket(client_ws: WebSocket, upstream) -> None:
    import asyncio

    async def c2u():
        try:
            while True:
                msg = await client_ws.receive_text()
                await upstream.send(msg)
        except WebSocketDisconnect:
            await upstream.close()
        except Exception:  # noqa: BLE001
            await upstream.close()

    async def u2c():
        try:
            async for msg in upstream:
                if isinstance(msg, bytes):
                    await client_ws.send_bytes(msg)
                else:
                    await client_ws.send_text(msg)
        except Exception:  # noqa: BLE001
            pass
        finally:
            try:
                await client_ws.close()
            except Exception:  # noqa: BLE001
                pass

    import asyncio as _asyncio

    await _asyncio.gather(c2u(), u2c())
