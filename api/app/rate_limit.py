"""Límite de solicitudes por IP, en memoria (sirve con una sola instancia de la API).

Algoritmo de "ventana deslizante": por cada IP se guardan las horas de sus últimas
solicitudes aceptadas. Una solicitud nueva se acepta si, en cada ventana (p. ej. los
últimos 60 s), hay menos solicitudes que el máximo permitido.
"""

import ipaddress
import logging
import math
import time
from collections import deque
from collections.abc import Callable, Sequence
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)

# Cada cuántas solicitudes se borran de memoria las IP que ya no tienen marcas vigentes
CLEANUP_EVERY = 1000


class RateLimiter:
    def __init__(
        self,
        limits: Sequence[tuple[int, float]],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """`limits`: pares (máximo de solicitudes, ventana en segundos), p. ej. [(5, 60), (20, 86400)].

        `clock`: reloj monotónico (no retrocede si cambia la hora del sistema); las pruebas
        pasan uno falso para "adelantar el tiempo" sin esperar.
        """
        self.limits = list(limits)
        self.clock = clock
        self._max_window = max(window for _, window in self.limits)
        self._hits: dict[str, deque[float]] = {}
        # FastAPI ejecuta las rutas `def` en varios hilos: el Lock evita que dos solicitudes
        # de la misma IP lean y escriban su deque a la vez
        self._lock = Lock()
        self._calls = 0

    def hit(self, key: str) -> float | None:
        """Registra una solicitud de `key`. Devuelve None si se acepta, o los segundos que
        faltan para que vuelva a haber cupo si se rechaza."""
        now = self.clock()
        with self._lock:
            self._calls += 1
            if self._calls % CLEANUP_EVERY == 0:
                self._cleanup(now)

            hits = self._hits.setdefault(key, deque())
            # Descarta las marcas más viejas que la ventana más larga
            while hits and hits[0] <= now - self._max_window:
                hits.popleft()

            retry_after = 0.0
            for max_requests, window in self.limits:
                in_window = sum(1 for t in hits if t > now - window)
                if in_window >= max_requests:
                    # Habrá cupo cuando salga de la ventana la marca que hoy ocupa el último lugar permitido
                    retry_after = max(retry_after, hits[-max_requests] + window - now)

            if retry_after > 0:
                # Las rechazadas no se guardan: la memoria por IP queda acotada al límite mayor
                return retry_after
            hits.append(now)
            return None

    def reset(self) -> None:
        """Olvida todas las solicitudes (lo usan las pruebas)."""
        with self._lock:
            self._hits.clear()

    def _cleanup(self, now: float) -> None:
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] <= now - self._max_window]
        for key in stale:
            del self._hits[key]


def _parse_ip(value: str | None) -> str | None:
    """Devuelve la IP normalizada, o None si `value` no es una IP válida.

    Normalizar evita que la misma IPv6 escrita de dos formas tenga dos cupos distintos.
    """
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request: Request, header: str) -> str:
    """IP del visitante según CLIENT_IP_HEADER (ver config.py).

    Si el encabezado configurado falta o no trae una IP válida, se usa la IP de la
    conexión: así nadie elige su IP mandando basura en el encabezado.
    """
    ip = None
    if header == "cf-connecting-ip":
        # Cloudflare sobrescribe este encabezado con la IP que se conectó a él
        ip = _parse_ip(request.headers.get("cf-connecting-ip"))
    elif header == "x-forwarded-for":
        # Cada proxy AGREGA a la derecha la IP que vio; la izquierda la puede escribir el cliente.
        # getlist: el encabezado puede venir repetido en varias líneas.
        entries = ",".join(request.headers.getlist("x-forwarded-for")).split(",")
        ip = _parse_ip(entries[-1])
    if ip is None:
        ip = request.client.host if request.client else "unknown"
    return ip


def rate_limit(limiter: RateLimiter) -> Callable[..., None]:
    """Crea una dependencia de FastAPI que aplica `limiter` por IP del cliente.

    Uvicorn se ejecuta con --no-proxy-headers: `request.client` es siempre la conexión
    TCP real, y solo `client_ip()` decide si se confía en un encabezado de proxy.
    """

    def dependency(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> None:
        key = client_ip(request, settings.client_ip_header)
        retry_after = limiter.hit(key)
        if retry_after is not None:
            # Sin la IP: es dato personal (DESIGN §2.3)
            logger.warning("Límite de solicitudes alcanzado en %s", request.url.path)
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please try again later.",
                # Retry-After: segundos enteros que el cliente debería esperar
                headers={"Retry-After": str(max(1, math.ceil(retry_after)))},
            )

    return dependency
