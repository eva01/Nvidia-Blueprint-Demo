# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Small local school knowledge base retriever for RAG-style grounding."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from rapidfuzz import fuzz

from src.nvidia_rag_providers import NvidiaEmbeddingProvider, NvidiaRerankProvider


@dataclass(frozen=True)
class KnowledgeDocument:
    """A retrievable school knowledge-base chunk."""

    id: str
    title: str
    content: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class KnowledgeSearchResult(KnowledgeDocument):
    """A retrieved knowledge-base chunk with a relevance score."""

    score: float


class SchoolKnowledgeBase:
    """Searches small school policy and facility procedure chunks."""

    def __init__(self, documents: list[dict[str, Any] | KnowledgeDocument]) -> None:
        self.documents = tuple(_coerce_document(document) for document in documents)

    def search(self, query: str, *, limit: int = 3, min_score: float = 35) -> list[KnowledgeSearchResult]:
        """Return relevant documents for a user query."""
        normalized_query = query.strip()
        if not normalized_query:
            return []

        results: list[KnowledgeSearchResult] = []
        for document in self.documents:
            haystack = " ".join([document.title, document.content, " ".join(document.tags)])
            score = max(
                fuzz.token_set_ratio(normalized_query, haystack),
                fuzz.partial_ratio(normalized_query, haystack),
            )
            if score >= min_score:
                results.append(
                    KnowledgeSearchResult(
                        id=document.id,
                        title=document.title,
                        content=document.content,
                        tags=document.tags,
                        score=float(score),
                    )
                )

        return sorted(results, key=lambda result: result.score, reverse=True)[:limit]

    def build_prompt_context(self, query: str, *, limit: int = 3, min_score: float = 35) -> str:
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


def load_school_knowledge_base(path: Path | str | None = None) -> SchoolKnowledgeBase:
    """Load the configured school knowledge base."""
    kb_path = Path(path or "config/school_knowledge_base.yaml")
    payload = yaml.safe_load(kb_path.read_text(encoding="utf-8")) or {}
    documents = payload.get("documents")
    if not isinstance(documents, list):
        raise ValueError(f"{kb_path} must contain a documents list")
    documents = [*documents, *_load_markdown_documents()]
    backend = _knowledge_backend()
    if backend == "sqlite-vec":
        from src.school_vector_knowledge_base import SQLiteVectorKnowledgeBase

        knowledge_base = SQLiteVectorKnowledgeBase(
            Path(os.getenv("SCHOOL_VECTOR_DB_PATH", "data/school_knowledge_vectors.db")),
            NvidiaEmbeddingProvider(timeout=_env_int("NVIDIA_RAG_TIMEOUT_SECONDS", 30)),
            reranker=_load_reranker(),
        )
        knowledge_base.index_documents(documents)
        return knowledge_base
    if backend == "faiss":
        from src.school_faiss_knowledge_base import FAISSKnowledgeBase

        knowledge_base = FAISSKnowledgeBase(
            Path(os.getenv("SCHOOL_FAISS_INDEX_PATH", "data/school_knowledge.faiss")),
            NvidiaEmbeddingProvider(timeout=_env_int("NVIDIA_RAG_TIMEOUT_SECONDS", 30)),
            reranker=_load_reranker(),
        )
        knowledge_base.index_documents(documents)
        return knowledge_base
    return SchoolKnowledgeBase(documents)


def _knowledge_backend() -> str:
    return os.getenv("SCHOOL_KNOWLEDGE_BACKEND", "fuzzy").strip().lower()


def _load_reranker() -> NvidiaRerankProvider | None:
    if os.getenv("ENABLE_NVIDIA_RERANK", "false").lower() != "true":
        return None
    return NvidiaRerankProvider(timeout=_env_int("NVIDIA_RAG_TIMEOUT_SECONDS", 30))


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _load_markdown_documents() -> list[dict[str, Any]]:
    markdown_dir = os.getenv("SCHOOL_KNOWLEDGE_MARKDOWN_DIR", "").strip()
    if not markdown_dir:
        return []
    root = Path(markdown_dir)
    if not root.exists():
        return []
    return [_markdown_document(path) for path in sorted(root.glob("*.md"))]


def _markdown_document(path: Path) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    title = path.stem.replace("-", " ").title()
    tags: list[str] = []
    body: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and title == path.stem.replace("-", " ").title():
            title = stripped.removeprefix("# ").strip()
        elif stripped.lower().startswith("tags:"):
            tags = [tag.strip() for tag in stripped.removeprefix("Tags:").split(",") if tag.strip()]
        elif stripped:
            body.append(stripped)
    return {
        "id": path.stem,
        "title": title,
        "content": " ".join(body),
        "tags": tags,
    }


def _coerce_document(document: dict[str, Any] | KnowledgeDocument) -> KnowledgeDocument:
    if isinstance(document, KnowledgeDocument):
        return document
    tags = document.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    return KnowledgeDocument(
        id=str(document.get("id", "")).strip(),
        title=str(document.get("title", "")).strip(),
        content=str(document.get("content", "")).strip(),
        tags=tuple(str(tag).strip() for tag in tags if str(tag).strip()),
    )
