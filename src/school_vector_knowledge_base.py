# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""SQLite-backed school knowledge base with vector retrieval."""

from __future__ import annotations

import json
import math
import sqlite3
from pathlib import Path
from typing import Protocol

from src.school_knowledge_base import KnowledgeDocument, KnowledgeSearchResult, _coerce_document


class EmbeddingProvider(Protocol):
    """Embeds text for semantic retrieval."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text."""


class RerankProvider(Protocol):
    """Reranks retrieved candidate documents."""

    def rerank(self, query: str, documents: list[KnowledgeDocument], *, limit: int) -> list[KnowledgeDocument]:
        """Return documents in final relevance order."""


class SQLiteVectorKnowledgeBase:
    """Stores school KB chunks in SQLite and searches by vector similarity."""

    def __init__(
        self,
        db_path: Path | str,
        embedder: EmbeddingProvider,
        *,
        reranker: RerankProvider | None = None,
    ) -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._embedder = embedder
        self._reranker = reranker
        self._init_db()

    def index_documents(self, documents: list[dict | KnowledgeDocument]) -> None:
        """Replace the indexed documents with fresh embeddings."""
        coerced = [_coerce_document(document) for document in documents]
        texts = [_embedding_text(document) for document in coerced]
        if hasattr(self._embedder, "embed_documents"):
            vectors = self._embedder.embed_documents(texts)
        else:
            vectors = self._embedder.embed(texts)
        if len(vectors) != len(coerced):
            raise ValueError("embedding provider returned the wrong number of vectors")

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM school_knowledge_vectors")
            if _try_load_sqlite_vec(conn) and vectors:
                conn.execute("DROP TABLE IF EXISTS school_knowledge_vec_index")
                conn.execute(
                    f"CREATE VIRTUAL TABLE school_knowledge_vec_index USING vec0(embedding float[{len(vectors[0])}])"
                )
                import sqlite_vec

                for document, vector in zip(coerced, vectors, strict=True):
                    cursor = conn.execute(
                        """
                        INSERT INTO school_knowledge_vectors
                            (id, title, content, tags_json, embedding_json)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            document.id,
                            document.title,
                            document.content,
                            json.dumps(list(document.tags)),
                            json.dumps(_normalize_vector(vector)),
                        ),
                    )
                    conn.execute(
                        "INSERT INTO school_knowledge_vec_index(rowid, embedding) VALUES (?, ?)",
                        (cursor.lastrowid, sqlite_vec.serialize_float32(_normalize_vector(vector))),
                    )
            else:
                conn.executemany(
                    """
                    INSERT INTO school_knowledge_vectors
                        (id, title, content, tags_json, embedding_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            document.id,
                            document.title,
                            document.content,
                            json.dumps(list(document.tags)),
                            json.dumps(_normalize_vector(vector)),
                        )
                        for document, vector in zip(coerced, vectors, strict=True)
                    ],
                )

    def search(self, query: str, *, limit: int = 3, min_score: float = 0.0) -> list[KnowledgeSearchResult]:
        """Return semantically relevant documents for a query."""
        normalized_query = query.strip()
        if not normalized_query:
            return []

        if hasattr(self._embedder, "embed_query"):
            query_vector = _normalize_vector(self._embedder.embed_query(normalized_query))
        else:
            query_vector = _normalize_vector(self._embedder.embed([normalized_query])[0])
        candidates = self._load_candidates(query_vector, max(limit * 4, limit), min_score)
        if self._reranker and candidates:
            documents = [
                KnowledgeDocument(
                    id=candidate.id,
                    title=candidate.title,
                    content=candidate.content,
                    tags=candidate.tags,
                )
                for candidate in candidates
            ]
            ranked = self._reranker.rerank(query, documents, limit=limit)
            scores_by_id = {candidate.id: candidate.score for candidate in candidates}
            return [
                KnowledgeSearchResult(
                    id=document.id,
                    title=document.title,
                    content=document.content,
                    tags=document.tags,
                    score=scores_by_id.get(document.id, 0.0),
                )
                for document in ranked[:limit]
            ]
        return candidates[:limit]

    def build_prompt_context(self, query: str, *, limit: int = 3, min_score: float = 0.0) -> str:
        """Build concise cited context for LLM prompt injection."""
        results = self.search(query, limit=limit, min_score=min_score)
        if not results:
            return ""
        lines = [
            "Retrieved school knowledge base context. Use only when it helps answer the user's question.",
            "If the user is reporting a facility issue, continue ticket intake instead of answering policy questions.",
        ]
        for result in results:
            lines.append(f"[{result.id}] {result.title}: {result.content}")
        return "\n".join(lines)

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS school_knowledge_vectors (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags_json TEXT NOT NULL,
                    embedding_json TEXT NOT NULL
                )
                """
            )

    def _load_candidates(
        self,
        query_vector: list[float],
        limit: int,
        min_score: float,
    ) -> list[KnowledgeSearchResult]:
        with sqlite3.connect(self.db_path) as conn:
            if _try_load_sqlite_vec(conn) and _has_vec_table(conn):
                import sqlite_vec

                rows = conn.execute(
                    """
                    SELECT k.id, k.title, k.content, k.tags_json, v.distance
                    FROM school_knowledge_vec_index v
                    JOIN school_knowledge_vectors k ON k.rowid = v.rowid
                    WHERE v.embedding MATCH ? AND v.k = ?
                    ORDER BY v.distance
                    """,
                    (sqlite_vec.serialize_float32(query_vector), limit),
                ).fetchall()
                results = [
                    KnowledgeSearchResult(
                        id=row[0],
                        title=row[1],
                        content=row[2],
                        tags=tuple(json.loads(row[3])),
                        score=max(0.0, 100 - float(row[4])),
                    )
                    for row in rows
                    if max(0.0, 100 - float(row[4])) >= min_score
                ]
                return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

            rows = conn.execute(
                "SELECT id, title, content, tags_json, embedding_json FROM school_knowledge_vectors"
            ).fetchall()

        results = []
        for row in rows:
            score = _cosine_similarity(query_vector, json.loads(row[4])) * 100
            if score >= min_score:
                results.append(
                    KnowledgeSearchResult(
                        id=row[0],
                        title=row[1],
                        content=row[2],
                        tags=tuple(json.loads(row[3])),
                        score=score,
                    )
                )
        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]


def _embedding_text(document: KnowledgeDocument) -> str:
    return " ".join([document.title, document.content, " ".join(document.tags)])


def _normalize_vector(vector: list[float]) -> list[float]:
    return [float(value) for value in vector]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _try_load_sqlite_vec(conn: sqlite3.Connection) -> bool:
    try:
        import sqlite_vec

        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        return True
    except Exception:
        return False


def _has_vec_table(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'school_knowledge_vec_index'"
    ).fetchone()
    return row is not None
