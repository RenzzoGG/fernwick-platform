"""Métricas del tablero del panel. Igual que en services/quotes.py, todo se filtra por el
alcance del usuario (el demo solo cuenta filas ficticias; el admin, solo reales)."""

from datetime import date, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Quote, User
from app.models.base import QUOTE_STATUSES, SERVICES
from app.schemas.metrics import DailyCount, MetricsSummary
from app.schemas.quote import business_today
from app.services.quotes import scope_is_demo

DAYS = 30

# generate_series crea una fila por día aunque no haya cotizaciones; el LEFT JOIN conserva
# esos días con count(q.id) = 0 (count de una columna no cuenta los NULL).
# - El filtro is_demo va en el ON y no en el WHERE: en el WHERE descartaría los días sin
#   coincidencias (sus columnas de q son NULL) y volverían los huecos.
# - Cada día se compara como un rango de instantes [00:00, 00:00 del día siguiente) en la zona
#   del negocio: así se puede usar el índice (is_demo, created_at) y el cambio de horario no
#   descuadra los días. Los CAST a timestamp (sin zona) evitan que PostgreSQL use la zona de
#   la sesión, que no tiene por qué ser la del negocio.
LAST_DAYS_SQL = text(
    """
    SELECT d.day::date AS day, count(q.id) AS count
    FROM generate_series(
        CAST(:start AS timestamp), CAST(:end AS timestamp), interval '1 day'
    ) AS d(day)
    LEFT JOIN quotes AS q
        ON q.is_demo = :is_demo
        AND q.created_at >= d.day AT TIME ZONE :tz
        AND q.created_at < (d.day + interval '1 day') AT TIME ZONE :tz
    GROUP BY d.day
    ORDER BY d.day
    """
)


def _counts_by(session: Session, column, is_demo: bool, keys: tuple[str, ...]) -> dict[str, int]:
    rows = session.execute(
        select(column, func.count()).where(Quote.is_demo == is_demo).group_by(column)
    )
    # Parte de todas las claves en 0 y suma lo que encontró la base
    return dict.fromkeys(keys, 0) | {key: count for key, count in rows}


def metrics_summary(session: Session, viewer: User, today: date | None = None) -> MetricsSummary:
    """Resumen del tablero. `today` se puede fijar en las pruebas; por defecto, hoy en la zona
    del negocio (BUSINESS_TIMEZONE)."""
    is_demo = scope_is_demo(viewer)
    today = today or business_today()

    by_status = _counts_by(session, Quote.status, is_demo, QUOTE_STATUSES)
    by_service = _counts_by(session, Quote.service, is_demo, SERVICES)
    rows = session.execute(
        LAST_DAYS_SQL,
        {
            "start": today - timedelta(days=DAYS - 1),
            "end": today,
            "is_demo": is_demo,
            "tz": get_settings().business_timezone,
        },
    )
    return MetricsSummary(
        # Cada cotización tiene exactamente un estado: el total es la suma
        total=sum(by_status.values()),
        by_status=by_status,
        by_service=by_service,
        last_30_days=[DailyCount(date=day, count=count) for day, count in rows],
    )
