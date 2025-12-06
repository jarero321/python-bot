"""
Embeddings para RAG usando sentence-transformers.
"""

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# Modelo de embeddings (384 dimensiones)
MODEL_NAME = "all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    """Obtiene el modelo de embeddings (singleton)."""
    global _model
    if _model is None:
        logger.info(f"Cargando modelo de embeddings: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


async def get_embedding(text: str) -> list[float]:
    """
    Genera embedding para un texto.

    Args:
        text: Texto a convertir

    Returns:
        Vector de 384 dimensiones
    """
    model = get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


async def get_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """
    Genera embeddings para múltiples textos.

    Args:
        texts: Lista de textos

    Returns:
        Lista de vectores
    """
    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return [e.tolist() for e in embeddings]


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """Calcula similitud coseno entre dos vectores."""
    import numpy as np

    a = np.array(vec1)
    b = np.array(vec2)

    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
