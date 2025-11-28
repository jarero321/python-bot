"""Servicio de Telegram para enviar mensajes."""

import logging

from telegram import Bot
from telegram.constants import ParseMode

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramService:
    """Cliente para interactuar con Telegram Bot API."""

    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)
        self.chat_id = settings.telegram_chat_id

    async def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = ParseMode.HTML,
    ) -> bool:
        """Envía un mensaje de texto."""
        target_chat = chat_id or self.chat_id
        try:
            await self.bot.send_message(
                chat_id=target_chat,
                text=text,
                parse_mode=parse_mode,
            )
            logger.info(f"Mensaje enviado a {target_chat}")
            return True
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")
            return False

    async def send_message_with_keyboard(
        self,
        text: str,
        reply_markup,
        chat_id: str | None = None,
        parse_mode: str = ParseMode.HTML,
    ) -> bool:
        """Envía un mensaje con teclado inline."""
        target_chat = chat_id or self.chat_id
        try:
            await self.bot.send_message(
                chat_id=target_chat,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            logger.info(f"Mensaje con keyboard enviado a {target_chat}")
            return True
        except Exception as e:
            logger.error(f"Error enviando mensaje con keyboard: {e}")
            return False


# Singleton
_telegram_service: TelegramService | None = None


def get_telegram_service() -> TelegramService:
    """Obtiene la instancia del servicio de Telegram."""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service
