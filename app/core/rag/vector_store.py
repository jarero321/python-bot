"""
Vector Store - Almacenamiento y búsqueda de vectores.

Implementación en memoria con persistencia opcional a SQLite.
Diseñado para escala pequeña-mediana (< 100k documentos).
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.rag.embeddings import EmbeddingProvider, get_embedding_provider

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Documento almacenado en el vector store."""

    id: str
    content: str
    embedding: list[float] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SearchResult:
    """Resultado de búsqueda."""

    document: Document
    score: float  # Similitud 0-1
    rank: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.document.id,
            "content": self.document.content,
            "metadata": self.document.metadata,
            "score": self.score,
            "rank": self.rank,
        }


class VectorStore:
    """
    Almacén de vectores en memoria con persistencia SQLite.

    Uso:
        store = get_vector_store()
        await store.add("task_123", "Revisar emails", {"type": "task"})
        results = await store.search("emails pendientes", limit=5)
    """

    _instance: "VectorStore | None" = None

    def __new__(cls, *args, **kwargs) -> "VectorStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        db_path: str | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self._documents: dict[str, Document] = {}
        self._embedding_provider = embedding_provider or get_embedding_provider()
        self._db_path = db_path or "data/vectors.db"
        self._db_loaded = False

    async def initialize(self) -> None:
        """Inicializa el store y carga datos persistidos."""
        if self._db_loaded:
            return

        self._embedding_provider.ensure_configured()
        self._load_from_db()
        self._db_loaded = True
        logger.info(f"VectorStore inicializado con {len(self._documents)} documentos")

    def _load_from_db(self) -> None:
        """Carga documentos desde SQLite."""
        try:
            path = Path(self._db_path)
            if not path.exists():
                path.parent.mkdir(parents=True, exist_ok=True)
                self._create_db()
                return

            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, content, embedding, metadata, created_at
                FROM documents
            """)

            for row in cursor.fetchall():
                doc_id, content, embedding_json, metadata_json, created_at = row
                self._documents[doc_id] = Document(
                    id=doc_id,
                    content=content,
                    embedding=json.loads(embedding_json),
                    metadata=json.loads(metadata_json),
                    created_at=datetime.fromisoformat(created_at),
                )

            conn.close()
        except Exception as e:
            logger.error(f"Error cargando VectorStore: {e}")

    def _create_db(self) -> None:
        """Crea la base de datos SQLite."""
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                embedding TEXT NOT NULL,
                metadata TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON documents(created_at)
        """)

        conn.commit()
        conn.close()

    def _save_document(self, doc: Document) -> None:
        """Guarda un documento en SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO documents (id, content, embedding, metadata, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                doc.id,
                doc.content,
                json.dumps(doc.embedding),
                json.dumps(doc.metadata),
                doc.created_at.isoformat(),
            ))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error guardando documento: {e}")

    def _delete_document(self, doc_id: str) -> None:
        """Elimina un documento de SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error eliminando documento: {e}")

    # ==================== Public API ====================

    async def add(
        self,
        id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """
        Agrega un documento al store.

        Args:
            id: ID único del documento
            content: Contenido textual
            metadata: Metadatos adicionales (type, source, etc.)

        Returns:
            Documento creado
        """
        await self.initialize()

        # Generar embedding
        embedding = await self._embedding_provider.embed(content)

        doc = Document(
            id=id,
            content=content,
            embedding=embedding,
            metadata=metadata or {},
        )

        self._documents[id] = doc
        self._save_document(doc)

        logger.debug(f"Documento agregado: {id}")
        return doc

    async def add_batch(
        self,
        items: list[tuple[str, str, dict[str, Any] | None]],
    ) -> list[Document]:
        """
        Agrega múltiples documentos.

        Args:
            items: Lista de (id, content, metadata)

        Returns:
            Lista de documentos creados
        """
        await self.initialize()

        # Generar embeddings en batch
        contents = [item[1] for item in items]
        embeddings = await self._embedding_provider.embed_batch(contents)

        docs = []
        for (doc_id, content, metadata), embedding in zip(items, embeddings):
            doc = Document(
                id=doc_id,
                content=content,
                embedding=embedding,
                metadata=metadata or {},
            )
            self._documents[doc_id] = doc
            self._save_document(doc)
            docs.append(doc)

        logger.info(f"Agregados {len(docs)} documentos en batch")
        return docs

    async def get(self, id: str) -> Document | None:
        """Obtiene un documento por ID."""
        await self.initialize()
        return self._documents.get(id)

    async def delete(self, id: str) -> bool:
        """Elimina un documento."""
        await self.initialize()

        if id in self._documents:
            del self._documents[id]
            self._delete_document(id)
            return True
        return False

    async def search(
        self,
        query: str,
        limit: int = 10,
        min_score: float = 0.0,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Busca documentos similares a la query.

        Args:
            query: Texto de búsqueda
            limit: Número máximo de resultados
            min_score: Puntuación mínima (0-1)
            filter_metadata: Filtrar por metadatos

        Returns:
            Lista de resultados ordenados por similitud
        """
        await self.initialize()

        if not self._documents:
            return []

        # Generar embedding de la query
        query_embedding = await self._embedding_provider.embed_query(query)

        # Calcular similitudes
        results: list[tuple[Document, float]] = []

        for doc in self._documents.values():
            # Aplicar filtro de metadata si existe
            if filter_metadata:
                match = all(
                    doc.metadata.get(k) == v
                    for k, v in filter_metadata.items()
                )
                if not match:
                    continue

            # Calcular similitud
            score = self._cosine_similarity(query_embedding, doc.embedding)

            if score >= min_score:
                results.append((doc, score))

        # Ordenar por score descendente
        results.sort(key=lambda x: x[1], reverse=True)

        # Crear SearchResults
        return [
            SearchResult(document=doc, score=score, rank=i + 1)
            for i, (doc, score) in enumerate(results[:limit])
        ]

    async def find_similar(
        self,
        id: str,
        limit: int = 5,
        min_score: float = 0.5,
    ) -> list[SearchResult]:
        """
        Encuentra documentos similares a uno existente.

        Args:
            id: ID del documento de referencia
            limit: Número máximo de resultados
            min_score: Puntuación mínima

        Returns:
            Lista de documentos similares (excluyendo el original)
        """
        await self.initialize()

        doc = self._documents.get(id)
        if not doc:
            return []

        results: list[tuple[Document, float]] = []

        for other_id, other_doc in self._documents.items():
            if other_id == id:
                continue

            score = self._cosine_similarity(doc.embedding, other_doc.embedding)
            if score >= min_score:
                results.append((other_doc, score))

        results.sort(key=lambda x: x[1], reverse=True)

        return [
            SearchResult(document=d, score=s, rank=i + 1)
            for i, (d, s) in enumerate(results[:limit])
        ]

    async def exists(self, id: str) -> bool:
        """Verifica si existe un documento."""
        await self.initialize()
        return id in self._documents

    @property
    def count(self) -> int:
        """Número de documentos en el store."""
        return len(self._documents)

    @staticmethod
    def _cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        """Calcula similitud coseno."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = sum(a * a for a in vec1) ** 0.5
        norm2 = sum(b * b for b in vec2) ** 0.5

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return dot_product / (norm1 * norm2)


# Singleton
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Obtiene la instancia del VectorStore."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
