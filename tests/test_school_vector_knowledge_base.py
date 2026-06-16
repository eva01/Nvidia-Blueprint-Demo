import tempfile
import unittest
from pathlib import Path

from src.school_knowledge_base import KnowledgeDocument
from src.school_vector_knowledge_base import (
    EmbeddingProvider,
    RerankProvider,
    SQLiteVectorKnowledgeBase,
)


class FakeEmbedder(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "visitor" in lowered or "register" in lowered else 0.0,
                    1.0 if "water" in lowered or "socket" in lowered else 0.0,
                ]
            )
        return vectors


class PreferVisitorReranker(RerankProvider):
    def rerank(self, query: str, documents: list[KnowledgeDocument], *, limit: int) -> list[KnowledgeDocument]:
        return sorted(documents, key=lambda document: document.id != "visitor-policy")[:limit]


class SQLiteVectorKnowledgeBaseTests(unittest.TestCase):
    def test_indexes_documents_and_searches_by_embedding_similarity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            kb = SQLiteVectorKnowledgeBase(Path(temp_dir) / "kb.db", FakeEmbedder())
            kb.index_documents(
                [
                    {
                        "id": "visitor-policy",
                        "title": "Visitor policy",
                        "content": "Visitors must register at the main office.",
                        "tags": ["security"],
                    },
                    {
                        "id": "water-electricity",
                        "title": "Water near electricity",
                        "content": "Water near sockets is urgent.",
                        "tags": ["safety"],
                    },
                ]
            )

            results = kb.search("where should visitors register", limit=1)

            self.assertEqual(results[0].id, "visitor-policy")
            self.assertGreater(results[0].score, 0)

    def test_reranker_can_rescore_vector_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            kb = SQLiteVectorKnowledgeBase(Path(temp_dir) / "kb.db", FakeEmbedder(), reranker=PreferVisitorReranker())
            kb.index_documents(
                [
                    {
                        "id": "water-electricity",
                        "title": "Water near electricity",
                        "content": "Water near sockets is urgent.",
                        "tags": ["safety"],
                    },
                    {
                        "id": "visitor-policy",
                        "title": "Visitor policy",
                        "content": "Visitors must register at the main office.",
                        "tags": ["security"],
                    },
                ]
            )

            results = kb.search("water visitor", limit=1)

            self.assertEqual(results[0].id, "visitor-policy")


if __name__ == "__main__":
    unittest.main()
