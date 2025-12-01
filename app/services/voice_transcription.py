"""
Voice Transcription Service - Transcribe audio usando Google Gemini.

Soporta mensajes de voz de Telegram (formato OGG/OPUS).
"""

import logging
import tempfile
from pathlib import Path

import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VoiceTranscriptionService:
    """Servicio para transcribir audio usando Gemini."""

    def __init__(self):
        self._configured = False
        self._model = None

    def _ensure_configured(self):
        """Configura el cliente de Gemini si no está configurado."""
        if not self._configured:
            genai.configure(api_key=settings.gemini_api_key)
            # Usar modelo flash para transcripción (más rápido)
            self._model = genai.GenerativeModel("gemini-2.0-flash-exp")
            self._configured = True
            logger.info("VoiceTranscriptionService configurado")

    async def transcribe_audio(self, audio_bytes: bytes, mime_type: str = "audio/ogg") -> str:
        """
        Transcribe audio a texto.

        Args:
            audio_bytes: Bytes del archivo de audio
            mime_type: Tipo MIME del audio (default: audio/ogg para Telegram)

        Returns:
            Texto transcrito
        """
        self._ensure_configured()

        try:
            # Guardar temporalmente el audio
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_file:
                tmp_file.write(audio_bytes)
                tmp_path = tmp_file.name

            # Subir archivo a Gemini
            audio_file = genai.upload_file(tmp_path, mime_type=mime_type)

            # Prompt para transcripción
            prompt = """Transcribe el siguiente audio a texto en español.

            Reglas:
            - Solo devuelve el texto transcrito, sin explicaciones
            - Si hay ruido o partes inaudibles, indica [inaudible]
            - Mantén la puntuación natural
            - Si el audio está vacío o es solo ruido, responde: [audio vacío]
            """

            # Generar transcripción
            response = self._model.generate_content([prompt, audio_file])

            # Limpiar archivo temporal
            Path(tmp_path).unlink(missing_ok=True)

            # Limpiar archivo subido
            try:
                audio_file.delete()
            except Exception:
                pass

            transcription = response.text.strip()
            logger.info(f"Audio transcrito: {len(transcription)} caracteres")

            return transcription

        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            raise


# Singleton
_voice_service: VoiceTranscriptionService | None = None


def get_voice_service() -> VoiceTranscriptionService:
    """Obtiene la instancia del servicio de voz."""
    global _voice_service
    if _voice_service is None:
        _voice_service = VoiceTranscriptionService()
    return _voice_service
