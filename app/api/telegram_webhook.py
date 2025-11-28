"""Webhook endpoint para Telegram."""

import logging

from fastapi import APIRouter, Request
from telegram import Update

from app.bot.handlers import get_application

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["webhook"])


@router.post("/telegram")
async def telegram_webhook(request: Request):
    """Procesa los updates de Telegram via webhook."""
    try:
        data = await request.json()
        logger.debug(f"Update recibido: {data}")

        application = await get_application()
        update = Update.de_json(data, application.bot)

        await application.process_update(update)

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error procesando webhook: {e}")
        return {"status": "error", "message": str(e)}
