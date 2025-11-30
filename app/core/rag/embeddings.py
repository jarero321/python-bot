"""
Embedding Provider - Generación de embeddings usando Gemini.

Proporciona embeddings vectoriales para texto, permitiendo
búsqueda semántica y detección de similitud.
"""

import logging
from typing import Any

import google.generativeai as genai

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingProvider:
    """
    Proveedor de embeddings usando Google Gemini.

    Uso:
        provider = get_embedding_provider()
        embedding = await provider.embed("Mi texto")
        embeddings = await provider.embed_batch(["Texto 1", "Texto 2"])
    """

    _instance: "EmbeddingProvider | None" = None
    _configured: bool = False

    # Modelo de embeddings de Gemini
    MODEL_NAME = "models/embedding-001"
    EMBEDDING_DIMENSION = 768  # Dimensión de embedding-001

    def __new__(cls) -> "EmbeddingProvider":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._model = None

    def configure(self) -> None:
        """Configura el proveedor de embeddings."""
        if self._configured:
            return

        try:
            genai.configure(api_key=settings.gemini_api_key)
            self._configured = True
            logger.info(f"EmbeddingProvider configurado: {self.MODEL_NAME}")
        except Exception as e:
            logger.error(f"Error configurando EmbeddingProvider: {e}")
            raise

    def ensure_configured(self) -> None:
        """Asegura que el proveedor esté configurado."""
        if not self._configured:
            self.configure()

    async def embed(self, text: str, task_type: str = "retrieval_document") -> list[float]:
        """
        Genera embedding para un texto.

        Args:
            text: Texto a embeber
            task_type: Tipo de tarea (retrieval_document, retrieval_query, etc.)

        Returns:
            Vector de embedding
        """
        self.ensure_configured()

        try:
            # Limpiar texto
            text = text.strip()
            if not text:
                return [0.0] * self.EMBEDDING_DIMENSION

            result = genai.embed_content(
                model=self.MODEL_NAME,
                content=text,
                task_type=task_type,
            )

            return result["embedding"]

        except Exception as e:
            logger.error(f"Error generando embedding: {e}")
            # Retornar vector cero en caso de error
            return [0.0] * self.EMBEDDING_DIMENSION

    async def embed_batch(
        self,
        texts: list[str],
        task_type: str = "retrieval_document",
    ) -> list[list[float]]:
        """
        Genera embeddings para múltiples textos.

        Args:
            texts: Lista de textos
            task_type: Tipo de tarea

        Returns:
            Lista de vectores de embedding
        """
        self.ensure_configured()

        try:
            # Limpiar textos
            cleaned = [t.strip() for t in texts]

            # Gemini soporta batch embedding
            result = genai.embed_content(
                model=self.MODEL_NAME,
                content=cleaned,
                task_type=task_type,
            )

            return result["embedding"]

        except Exception as e:
            logger.error(f"Error generando embeddings batch: {e}")
            # Retornar vectores cero
            return [[0.0] * self.EMBEDDING_DIMENSION for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        """
        Genera embedding para una query de búsqueda.

        Usa task_type optimizado para queries.
        """
        return await self.embed(query, task_type="retrieval_query")

    async def similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similitud coseno entre dos textos.

        Returns:
            Similitud entre 0 y 1
        """
        emb1 = await self.embed(text1)
        emb2 = await self.embed(text2)

        return self._cosine_similarity(emb1, emb2)

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calcula similitud coseno entre dos vectores."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# Singleton
_embedding_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """Obtiene la instancia del EmbeddingProvider."""
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = EmbeddingProvider()
    return _embedding_provider
