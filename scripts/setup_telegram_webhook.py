#!/usr/bin/env python3
"""Script para configurar el webhook de Telegram."""

import asyncio
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx


async def get_ngrok_url() -> str | None:
    """Obtiene la URL pública de ngrok."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:4040/api/tunnels")
            data = response.json()
            for tunnel in data.get("tunnels", []):
                if tunnel.get("proto") == "https":
                    return tunnel.get("public_url")
    except Exception as e:
        print(f"Error obteniendo URL de ngrok: {e}")
    return None


async def setup_webhook(bot_token: str, webhook_url: str) -> bool:
    """Configura el webhook en Telegram."""
    api_url = f"https://api.telegram.org/bot{bot_token}/setWebhook"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            api_url,
            json={"url": webhook_url}
        )
        data = response.json()

        if data.get("ok"):
            print(f"Webhook configurado exitosamente: {webhook_url}")
            return True
        else:
            print(f"Error: {data.get('description')}")
            return False


async def get_webhook_info(bot_token: str) -> dict:
    """Obtiene información del webhook actual."""
    api_url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"

    async with httpx.AsyncClient() as client:
        response = await client.get(api_url)
        return response.json()


async def delete_webhook(bot_token: str) -> bool:
    """Elimina el webhook actual."""
    api_url = f"https://api.telegram.org/bot{bot_token}/deleteWebhook"

    async with httpx.AsyncClient() as client:
        response = await client.post(api_url)
        data = response.json()
        return data.get("ok", False)


async def main():
    from app.config import get_settings

    settings = get_settings()
    bot_token = settings.telegram_bot_token

    if not bot_token:
        print("Error: TELEGRAM_BOT_TOKEN no está configurado")
        return

    print("=== Telegram Webhook Setup ===\n")

    # Mostrar info actual
    print("Info del webhook actual:")
    info = await get_webhook_info(bot_token)
    current_url = info.get("result", {}).get("url", "No configurado")
    print(f"  URL: {current_url}\n")

    # Intentar obtener URL de ngrok
    ngrok_url = await get_ngrok_url()

    if ngrok_url:
        webhook_url = f"{ngrok_url}/webhook/telegram"
        print(f"URL de ngrok detectada: {ngrok_url}")
        print(f"Webhook URL: {webhook_url}\n")

        response = input("¿Configurar este webhook? (s/n): ")
        if response.lower() == "s":
            await setup_webhook(bot_token, webhook_url)
    else:
        print("No se detectó ngrok corriendo en localhost:4040")
        print("Asegúrate de que docker-compose esté corriendo.\n")

        manual_url = input("Ingresa la URL del webhook manualmente (o Enter para salir): ")
        if manual_url:
            await setup_webhook(bot_token, manual_url)


if __name__ == "__main__":
    asyncio.run(main())
