# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""NVIDIA hosted RAG provider adapters."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.school_knowledge_base import KnowledgeDocument

JsonPost = Callable[[str, dict[str, str], dict[str, Any], int], dict[str, Any]]


class NvidiaEmbeddingProvider:
    """OpenAI-compatible NVIDIA embedding endpoint adapter."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 30,
        post_json: JsonPost = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("NVIDIA_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("NVIDIA_EMBED_URL", "https://integrate.api.nvidia.com/v1")).rstrip("/")
        self.model = (model or os.getenv("NVIDIA_EMBED_MODEL", "nvidia/llama-nemotron-embed-vl-1b-v2")).strip()
        self.timeout = timeout
        self._post_json = post_json or _post_json
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is required for sqlite-vec NVIDIA embedding")

    def embed(self, texts: list[str], *, input_type: str | None = None) -> list[list[float]]:
        """Embed text through the configured NVIDIA endpoint."""
        payload = {"model": self.model, "input": texts}
        if input_type:
            payload["input_type"] = input_type
        response = self._post_json(
            f"{self.base_url}/embeddings",
            _headers(self.api_key),
            payload,
            self.timeout,
        )
        return [[float(value) for value in item["embedding"]] for item in response.get("data", [])]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed corpus passages for retrieval indexing."""
        return self.embed(texts, input_type="passage")

    def embed_query(self, text: str) -> list[float]:
        """Embed a search query for asymmetric retrieval."""
        return self.embed([text], input_type="query")[0]


class NvidiaRerankProvider:
    """NVIDIA reranking endpoint adapter."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 30,
        post_json: JsonPost = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("NVIDIA_API_KEY", "")).strip()
        self.base_url = (
            base_url
            or os.getenv("NVIDIA_RERANK_URL", "https://ai.api.nvidia.com/v1/retrieval/nvidia/reranking")
        ).rstrip("/")
        self.model = (model or os.getenv("NVIDIA_RERANK_MODEL", "nvidia/llama-nemotron-rerank-vl-1b-v2")).strip()
        self.timeout = timeout
        self._post_json = post_json or _post_json
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is required for NVIDIA reranking")

    def rerank(self, query: str, documents: list[KnowledgeDocument], *, limit: int) -> list[KnowledgeDocument]:
        """Rerank candidate documents by NVIDIA relevance scores."""
        payload = {
            "model": self.model,
            "query": query,
            "passages": [_document_text(document) for document in documents],
        }
        response = self._post_json(self.base_url, _headers(self.api_key), payload, self.timeout)
        rankings = response.get("rankings") or response.get("data") or response.get("results") or []
        ordered_indexes = []
        for item in rankings:
            if "index" in item:
                ordered_indexes.append(int(item["index"]))
            elif "passage_index" in item:
                ordered_indexes.append(int(item["passage_index"]))
        if not ordered_indexes:
            return documents[:limit]
        return [documents[index] for index in ordered_indexes if 0 <= index < len(documents)][:limit]


class NvidiaSafetyGuardProvider:
    """NVIDIA Nemotron Safety Guard adapter."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 30,
        post_json: JsonPost = None,
    ) -> None:
        self.api_key = (api_key or os.getenv("NVIDIA_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("NVIDIA_SAFETY_URL", "https://integrate.api.nvidia.com/v1")).rstrip("/")
        self.model = (model or os.getenv("NVIDIA_SAFETY_MODEL", "nvidia/llama-3.1-nemotron-safety-guard-8b-v3")).strip()
        self.timeout = timeout
        self._post_json = post_json or _post_json
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is required for NVIDIA Safety Guard")

    def is_safe(self, text: str) -> bool:
        """Return true when Safety Guard marks the content as safe."""
        response = self._post_json(
            f"{self.base_url}/chat/completions",
            _headers(self.api_key),
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": "Classify whether this assistant response is safe to speak to a school user.",
                    },
                    {"role": "assistant", "content": text},
                ],
                "temperature": 0,
                "max_tokens": 32,
            },
            self.timeout,
        )
        content = _extract_chat_content(response).lower()
        unsafe_markers = ("unsafe", "not safe", "violation", "blocked")
        safe_markers = ("safe", "allowed", "pass")
        if any(marker in content for marker in unsafe_markers):
            return False
        return any(marker in content for marker in safe_markers)


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"NVIDIA RAG request failed with HTTP {exc.code}: {body}") from exc


def _document_text(document: KnowledgeDocument) -> str:
    return f"{document.title}\n{document.content}"


def _extract_chat_content(response: dict[str, Any]) -> str:
    choices = response.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content", ""))
