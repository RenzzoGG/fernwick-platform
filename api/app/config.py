"""Configuración de la API leída de variables de entorno (y de `.env` en desarrollo)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    # Las variables de entorno reales tienen prioridad sobre el archivo .env.
    # extra="ignore": otras variables del .env (de fases futuras) no rompen el arranque.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    # Sin valor por defecto: si falta, la API falla al arrancar con un error claro
    database_url: str
    # Solo para pytest; opcional para que la API arranque sin ella (p. ej. en Railway)
    test_database_url: str | None = None
    # Orígenes (páginas web) que pueden llamar a la API desde el navegador.
    # NoDecode: se lee como texto "a,b,c" y no como JSON. Vacío = ningún origen permitido.
    cors_origins: Annotated[list[str], NoDecode] = []

    @field_validator("database_url", "test_database_url")
    @classmethod
    def usar_driver_psycopg(cls, value: str | None) -> str | None:
        # Railway entrega "postgresql://..."; SQLAlchemy usaría psycopg2 (no instalado).
        # Se indica explícitamente el driver psycopg 3.
        if value is None:
            return None
        for prefijo in ("postgres://", "postgresql://"):
            if value.startswith(prefijo):
                return "postgresql+psycopg://" + value.removeprefix(prefijo)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def separar_origenes(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            value = value.split(",")
        # rstrip("/"): el navegador envía el Origin sin barra final
        origins = [origin.strip().rstrip("/") for origin in value if origin.strip()]
        if "*" in origins:
            raise ValueError("CORS_ORIGINS no admite '*': lista los orígenes explícitamente")
        return origins

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    # lru_cache: se lee el entorno una sola vez y se reutiliza el mismo objeto
    return Settings()
