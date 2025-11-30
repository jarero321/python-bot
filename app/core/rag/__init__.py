"""
RAG Module - Retrieval Augmented Generation.

Sistema de búsqueda semántica usando embeddings para:
- Encontrar tareas/proyectos similares
- Detectar duplicados
- Enriquecer contexto para LLM
- Sugerir basado en historial
"""

from app.core.rag.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
)
from app.core.rag.vector_store import (
    VectorStore,
    SearchResult,
    get_vector_store,
)
from app.core.rag.retriever import (
    RAGRetriever,
    get_retriever,
)

__all__ = [
    "EmbeddingProvider",
    "get_embedding_provider",
    "VectorStore",
    "SearchResult",
    "get_vector_store",
    "RAGRetriever",
    "get_retriever",
]
