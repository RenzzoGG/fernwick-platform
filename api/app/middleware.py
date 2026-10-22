"""Middlewares propios de la API."""

from fastapi import HTTPException
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

TOO_LARGE_DETAIL = "Request body too large"


class BodySizeLimitMiddleware:
    """Rechaza con 413 los cuerpos de solicitud que superan `max_bytes`.

    Es un middleware ASGI "puro" (no BaseHTTPMiddleware): envuelve la función `receive`
    con la que la app lee el cuerpo, así puede contar los bytes sin cargarlo entero antes.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # 1) Si el cliente declara el tamaño (Content-Length), se rechaza sin leer nada
        headers = dict(scope["headers"])
        content_length = headers.get(b"content-length")
        if content_length is not None and content_length.isdigit() and int(content_length) > self.max_bytes:
            response = JSONResponse(status_code=413, content={"detail": TOO_LARGE_DETAIL})
            await response(scope, receive, send)
            return

        # 2) Sin Content-Length (envío por partes, "chunked") o si miente: se cuentan los
        # bytes a medida que la app los lee. FastAPI deja pasar la HTTPException y responde 413.
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=413, detail=TOO_LARGE_DETAIL)
            return message

        await self.app(scope, limited_receive, send)
