"""Configuración de la API leída de variables de entorno (y de `.env` en desarrollo)."""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Las variables de entorno reales tienen prioridad sobre el archivo .env.
    # extra="ignore": otras variables del .env (de fases futuras) no rompen el arranque.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    # Sin valor por defecto: si falta, la API falla al arrancar con un error claro
    database_url: str

    @field_validator("database_url")
    @classmethod
    def usar_driver_psycopg(cls, value: str) -> str:
        # Railway entrega "postgresql://..."; SQLAlchemy usaría psycopg2 (no instalado).
        # Se indica explícitamente el driver psycopg 3.
        for prefijo in ("postgres://", "postgresql://"):
            if value.startswith(prefijo):
                return "postgresql+psycopg://" + value.removeprefix(prefijo)
        return value

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    # lru_cache: se lee el entorno una sola vez y se reutiliza el mismo objeto
    return Settings()
