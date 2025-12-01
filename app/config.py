"""Configuración de la aplicación usando Pydantic Settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración principal de Carlos Command."""

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

    # Notion
    notion_api_key: str = ""

    # Gemini
    gemini_api_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///data/carlos_command.db"

    # Timezone
    tz: str = "America/Mexico_City"

    # Ngrok
    ngrok_authtoken: str = ""

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache
def get_settings() -> Settings:
    """Obtiene la configuración cacheada."""
    return Settings()
