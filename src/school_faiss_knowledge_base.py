# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""FAISS-backed school knowledge base retrieval."""

from __future__ import annotations

import json
from pathlib import Path

import faiss
import numpy as np

from src.school_knowledge_base import KnowledgeDocument, KnowledgeSearchResult, _coerce_document
from src.school_vector_knowledge_base import EmbeddingProvider, RerankProvider, _embedding_text


class FAISSKnowledgeBase:
    """Stores school KB chunks in a local FAISS index."""

    def __init__(
        self,
        index_path: Path | str,
        embedder: EmbeddingProvider,
        *,
        reranker: RerankProvider | None = None,
    ) -> None:
        self.index_path = Path(index_path).expanduser().resolve()
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.index_path.with_suffix(f"{self.index_path.suffix}.json")
        self._embedder = embedder
        self._reranker = reranker
        self._documents: list[KnowledgeDocument] = []
        self._index = None

    def index_documents(self, documents: list[dict | KnowledgeDocument]) -> None:
        """Replace the FAISS index with fresh document embeddings."""
        self._documents = [_coerce_document(document) for document in documents]
        texts = [_embedding_text(document) for document in self._documents]
        vectors = self._embed_documents(texts)
        if len(vectors) != len(self._documents):
            raise ValueError("embedding provider returned the wrong number of vectors")
        matrix = _as_normalized_matrix(vectors)
        self._index = faiss.IndexFlatIP(matrix.shape[1])
        self._index.add(matrix)
        faiss.write_index(self._index, str(self.index_path))
        self.metadata_path.write_text(
            json.dumps(
                [
                    {
                        "id": document.id,
                        "title": document.title,
                        "content": document.content,
                        "tags": list(document.tags),
                    }
                    for document in self._documents
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

    def search(self, query: str, *, limit: int = 3, min_score: float = 0.0) -> list[KnowledgeSearchResult]:
        """Return semantically relevant documents from FAISS."""
        normalized_query = query.strip()
        if not normalized_query:
            return []
        self._ensure_loaded()
        if self._index is None or not self._documents:
            return []
        query_vector = _as_normalized_matrix([self._embed_query(normalized_query)])
        scores, indexes = self._index.search(query_vector, max(limit * 4, limit))
        candidates = []
        for score, index in zip(scores[0], indexes[0], strict=True):
            if index < 0:
                continue
            normalized_score = float(score) * 100
            if normalized_score >= min_score:
                document = self._documents[int(index)]
                candidates.append(
                    KnowledgeSearchResult(
                        id=document.id,
                        title=document.title,
                        content=document.content,
                        tags=document.tags,
                        score=normalized_score,
                    )
                )

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

    def _embed_documents(self, texts: list[str]) -> list[list[float]]:
        if hasattr(self._embedder, "embed_documents"):
            return self._embedder.embed_documents(texts)
        return self._embedder.embed(texts)

    def _embed_query(self, text: str) -> list[float]:
        if hasattr(self._embedder, "embed_query"):
            return self._embedder.embed_query(text)
        return self._embedder.embed([text])[0]

    def _ensure_loaded(self) -> None:
        if self._index is not None:
            return
        if self.index_path.exists() and self.metadata_path.exists():
            self._index = faiss.read_index(str(self.index_path))
            payload = json.loads(self.metadata_path.read_text(encoding="utf-8"))
            self._documents = [_coerce_document(document) for document in payload]


def _as_normalized_matrix(vectors: list[list[float]]) -> np.ndarray:
    matrix = np.asarray(vectors, dtype="float32")
    if matrix.ndim != 2:
        raise ValueError("embeddings must be a two-dimensional matrix")
    faiss.normalize_L2(matrix)
    return matrix
