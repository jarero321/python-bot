"""
Embeddings para RAG usando Google Gemini API.
Más ligero que sentence-transformers (no requiere PyTorch).
"""

import logging
import google.generativeai as genai
from app.config import get_settings

logger = logging.getLogger(__name__)

# Modelo de embeddings de Gemini (768 dimensiones)
MODEL_NAME = "models/text-embedding-004"

_configured = False


def _ensure_configured():
    """Configura la API de Gemini si no está configurada."""
    global _configured
    if not _configured:
        settings = get_settings()
        genai.configure(api_key=settings.gemini_api_key)
        _configured = True
        logger.info(f"Gemini embeddings configurado: {MODEL_NAME}")


async def get_embedding(text: str) -> list[float]:
    """
    Genera embedding para un texto usando Gemini.

    Args:
        text: Texto a convertir

    Returns:
        Vector de 768 dimensiones
    """
    _ensure_configured()

    result = genai.embed_content(
        model=MODEL_NAME,
        content=text,
        task_type="retrieval_document"
    )

    return result["embedding"]


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Genera embeddings para múltiples textos.

    Args:
        texts: Lista de textos

    Returns:
        Lista de vectores
    """
    _ensure_configured()

    # Gemini soporta batch embedding
    result = genai.embed_content(
        model=MODEL_NAME,
        content=texts,
        task_type="retrieval_document"
    )

    return result["embedding"]


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calcula similitud coseno entre dos vectores."""
    import numpy as np

    a = np.array(vec1)
    b = np.array(vec2)

    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
