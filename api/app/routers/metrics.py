"""Endpoint del tablero de métricas del panel."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.errors import UNAUTHORIZED
from app.schemas.metrics import MetricsSummary
from app.services.metrics import metrics_summary

router = APIRouter(prefix="/v1/metrics", tags=["metrics"], responses=UNAUTHORIZED)


@router.get("/summary", response_model=MetricsSummary)
def get_metrics_summary(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MetricsSummary:
    return metrics_summary(db, user)
