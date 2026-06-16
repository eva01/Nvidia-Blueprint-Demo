import tempfile
import unittest
from pathlib import Path

from src.school_vector_knowledge_base import EmbeddingProvider


class FakeEmbedder(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            lowered = text.lower()
            vectors.append(
                [
                    1.0 if "visitor" in lowered or "register" in lowered else 0.0,
                    1.0 if "lost" in lowered or "found" in lowered or "items" in lowered else 0.0,
                    0.1,
                ]
            )
        return vectors


class FAISSKnowledgeBaseTests(unittest.TestCase):
    def test_faiss_backend_indexes_and_searches_documents(self) -> None:
        from src.school_faiss_knowledge_base import FAISSKnowledgeBase

        with tempfile.TemporaryDirectory() as temp_dir:
            kb = FAISSKnowledgeBase(Path(temp_dir) / "school.faiss", FakeEmbedder())
            kb.index_documents(
                [
                    {
                        "id": "visitor-policy",
                        "title": "Visitor policy",
                        "content": "Visitors must register at the main office.",
                        "tags": ["security"],
                    },
                    {
                        "id": "lost-and-found",
                        "title": "Lost and found",
                        "content": "Students bring found items to the front office.",
                        "tags": ["student-services"],
                    },
                ]
            )

            results = kb.search("where do students bring found items", limit=1)

            self.assertEqual(results[0].id, "lost-and-found")
            self.assertGreater(results[0].score, 0)


if __name__ == "__main__":
    unittest.main()
