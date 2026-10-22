"""Esquemas del tablero de métricas."""

from datetime import date

from pydantic import BaseModel


class DailyCount(BaseModel):
    date: date
    count: int


class MetricsSummary(BaseModel):
    total: int
    # Siempre con todas las claves (estados y servicios posibles), aunque valgan 0
    by_status: dict[str, int]
    by_service: dict[str, int]
    # Los últimos 30 días en la zona del negocio, del más antiguo a hoy, sin huecos
    last_30_days: list[DailyCount]
