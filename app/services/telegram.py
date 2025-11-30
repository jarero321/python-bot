"""Servicio de Telegram para enviar mensajes y manejar voz."""

import io
import logging
import os
import tempfile
from pathlib import Path

import httpx
from telegram import Bot, Voice, Audio
from telegram.constants import ParseMode

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TelegramService:
    """Cliente para interactuar con Telegram Bot API con soporte de voz."""

    def __init__(self):
        self.bot = Bot(token=settings.telegram_bot_token)
        self.chat_id = settings.telegram_chat_id

        # Directorio para archivos temporales de voz
        self.voice_temp_dir = Path(tempfile.gettempdir()) / "carlos_voice"
        self.voice_temp_dir.mkdir(exist_ok=True)

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

    # ==================== VOICE SUPPORT ====================

    async def download_voice(self, voice: Voice | Audio) -> Path | None:
        """
        Descarga un mensaje de voz de Telegram.

        Args:
            voice: Objeto Voice o Audio de Telegram

        Returns:
            Path al archivo descargado o None si falla
        """
        try:
            # Obtener archivo de Telegram
            file = await self.bot.get_file(voice.file_id)

            # Determinar extensión
            extension = ".ogg" if isinstance(voice, Voice) else ".mp3"
            local_path = self.voice_temp_dir / f"{voice.file_unique_id}{extension}"

            # Descargar
            await file.download_to_drive(local_path)
            logger.info(f"Voz descargada: {local_path}")

            return local_path

        except Exception as e:
            logger.error(f"Error descargando voz: {e}")
            return None

    async def transcribe_voice(self, voice_path: Path) -> str | None:
        """
        Transcribe un archivo de voz usando OpenAI Whisper API.

        Args:
            voice_path: Path al archivo de voz

        Returns:
            Texto transcrito o None si falla
        """
        # Verificar si hay API key de OpenAI configurada
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if not openai_api_key:
            logger.warning("OPENAI_API_KEY no configurada, usando transcripción alternativa")
            return await self._transcribe_with_gemini(voice_path)

        try:
            async with httpx.AsyncClient() as client:
                # Preparar archivo para enviar
                with open(voice_path, "rb") as audio_file:
                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {openai_api_key}"},
                        files={"file": (voice_path.name, audio_file, "audio/ogg")},
                        data={
                            "model": "whisper-1",
                            "language": "es",
                            "response_format": "text",
                        },
                        timeout=30.0,
                    )

                if response.status_code == 200:
                    text = response.text.strip()
                    logger.info(f"Transcripción exitosa: {text[:50]}...")
                    return text
                else:
                    logger.error(f"Error en Whisper API: {response.status_code} - {response.text}")
                    return None

        except Exception as e:
            logger.error(f"Error transcribiendo voz: {e}")
            return None

    async def _transcribe_with_gemini(self, voice_path: Path) -> str | None:
        """
        Transcribe usando Gemini como alternativa a Whisper.

        Args:
            voice_path: Path al archivo de voz

        Returns:
            Texto transcrito o None si falla
        """
        try:
            import google.generativeai as genai

            genai.configure(api_key=settings.gemini_api_key)

            # Subir archivo a Gemini
            audio_file = genai.upload_file(str(voice_path))

            # Usar modelo con capacidad de audio
            model = genai.GenerativeModel("gemini-2.0-flash")

            response = model.generate_content([
                "Transcribe el siguiente audio en español. "
                "Solo devuelve el texto transcrito, sin explicaciones adicionales.",
                audio_file,
            ])

            if response.text:
                text = response.text.strip()
                logger.info(f"Transcripción con Gemini: {text[:50]}...")
                return text

            return None

        except Exception as e:
            logger.error(f"Error transcribiendo con Gemini: {e}")
            return None

    async def send_voice_message(
        self,
        text: str,
        chat_id: str | None = None,
    ) -> bool:
        """
        Envía un mensaje de voz (TTS).

        Args:
            text: Texto a convertir en voz
            chat_id: ID del chat destino

        Returns:
            True si se envió correctamente
        """
        target_chat = chat_id or self.chat_id

        try:
            # Generar audio con TTS
            audio_path = await self._text_to_speech(text)

            if not audio_path:
                # Fallback: enviar como texto
                logger.warning("TTS falló, enviando como texto")
                return await self.send_message(text, chat_id)

            # Enviar como nota de voz
            with open(audio_path, "rb") as audio_file:
                await self.bot.send_voice(
                    chat_id=target_chat,
                    voice=audio_file,
                    caption=text[:200] if len(text) > 200 else None,
                )

            logger.info(f"Mensaje de voz enviado a {target_chat}")

            # Limpiar archivo temporal
            os.remove(audio_path)

            return True

        except Exception as e:
            logger.error(f"Error enviando mensaje de voz: {e}")
            return False

    async def _text_to_speech(self, text: str) -> Path | None:
        """
        Convierte texto a voz usando OpenAI TTS o alternativa.

        Args:
            text: Texto a convertir

        Returns:
            Path al archivo de audio generado
        """
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if openai_api_key:
            return await self._tts_openai(text, openai_api_key)
        else:
            return await self._tts_google(text)

    async def _tts_openai(self, text: str, api_key: str) -> Path | None:
        """TTS usando OpenAI."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": "tts-1",
                        "input": text,
                        "voice": "nova",  # Voz femenina agradable
                        "response_format": "opus",
                    },
                    timeout=30.0,
                )

                if response.status_code == 200:
                    output_path = self.voice_temp_dir / f"tts_{hash(text)}.opus"
                    with open(output_path, "wb") as f:
                        f.write(response.content)
                    return output_path
                else:
                    logger.error(f"Error en OpenAI TTS: {response.status_code}")
                    return None

        except Exception as e:
            logger.error(f"Error en TTS OpenAI: {e}")
            return None

    async def _tts_google(self, text: str) -> Path | None:
        """TTS usando Google Cloud TTS (si está disponible)."""
        try:
            # Intentar usar gTTS como alternativa simple
            from gtts import gTTS

            tts = gTTS(text=text, lang="es", slow=False)
            output_path = self.voice_temp_dir / f"tts_{hash(text)}.mp3"
            tts.save(str(output_path))

            return output_path

        except ImportError:
            logger.warning("gTTS no instalado, TTS no disponible")
            return None
        except Exception as e:
            logger.error(f"Error en TTS Google: {e}")
            return None

    async def process_voice_message(
        self,
        voice: Voice | Audio,
        chat_id: str | None = None,
    ) -> dict:
        """
        Procesa un mensaje de voz: descarga, transcribe y retorna resultado.

        Args:
            voice: Objeto Voice o Audio de Telegram
            chat_id: ID del chat para enviar confirmación

        Returns:
            Dict con transcription, duration, y status
        """
        result = {
            "transcription": None,
            "duration": voice.duration if hasattr(voice, "duration") else 0,
            "status": "pending",
            "error": None,
        }

        try:
            # 1. Descargar archivo
            voice_path = await self.download_voice(voice)
            if not voice_path:
                result["status"] = "download_error"
                result["error"] = "No se pudo descargar el audio"
                return result

            # 2. Transcribir
            transcription = await self.transcribe_voice(voice_path)
            if not transcription:
                result["status"] = "transcription_error"
                result["error"] = "No se pudo transcribir el audio"
                # Limpiar archivo
                os.remove(voice_path)
                return result

            result["transcription"] = transcription
            result["status"] = "success"

            # 3. Limpiar archivo temporal
            os.remove(voice_path)

            return result

        except Exception as e:
            logger.error(f"Error procesando mensaje de voz: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            return result

    def cleanup_temp_files(self, max_age_hours: int = 1) -> int:
        """
        Limpia archivos temporales antiguos.

        Args:
            max_age_hours: Edad máxima en horas

        Returns:
            Número de archivos eliminados
        """
        import time

        deleted = 0
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()

        try:
            for file_path in self.voice_temp_dir.iterdir():
                if file_path.is_file():
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        file_path.unlink()
                        deleted += 1

            if deleted > 0:
                logger.info(f"Limpiados {deleted} archivos temporales de voz")

        except Exception as e:
            logger.error(f"Error limpiando archivos temporales: {e}")

        return deleted


# Singleton
_telegram_service: TelegramService | None = None


def get_telegram_service() -> TelegramService:
    """Obtiene la instancia del servicio de Telegram."""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service
