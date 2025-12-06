"""Configuracion de la aplicacion usando Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion principal de Carlos Command - Brain."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Telegram
    telegram_bot_token: str = ""
    telegram_webhook_url: str = ""
    telegram_chat_id: str = ""

    # Gemini (LLM)
    gemini_api_key: str = ""

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "carlos_brain"
    postgres_user: str = "carlos"
    postgres_password: str = ""

    # Timezone
    tz: str = "America/Mexico_City"

    # Ngrok (development)
    ngrok_authtoken: str = ""

    @property
    def database_url(self) -> str:
        """URL de conexion a PostgreSQL."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuracion cacheada."""
    return Settings()
