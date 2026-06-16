import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.school_faiss_knowledge_base import FAISSKnowledgeBase
from src.school_knowledge_base import SchoolKnowledgeBase, load_school_knowledge_base
from src.school_vector_knowledge_base import EmbeddingProvider, SQLiteVectorKnowledgeBase


class FakeEmbedder(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0 if "visitor" in text.lower() else 0.0, 1.0] for text in texts]


class SchoolKnowledgeBaseTests(unittest.TestCase):
    def test_search_returns_relevant_policy_chunks(self) -> None:
        kb = SchoolKnowledgeBase(
            [
                {
                    "id": "after-hours-access",
                    "title": "After-hours access",
                    "content": "Students must be accompanied by staff after 6 PM.",
                    "tags": ["security", "access"],
                },
                {
                    "id": "water-leak",
                    "title": "Water leak safety",
                    "content": "Water near electrical outlets is urgent and facilities must isolate the area.",
                    "tags": ["safety", "facilities"],
                },
            ]
        )

        results = kb.search("what should we do about water near a socket", limit=1)

        self.assertEqual(results[0].id, "water-leak")
        self.assertIn("Water near electrical outlets", results[0].content)

    def test_prompt_context_is_short_and_cited(self) -> None:
        kb = SchoolKnowledgeBase(
            [
                {
                    "id": "visitor-policy",
                    "title": "Visitor policy",
                    "content": "Visitors must register at the main office and wear a badge.",
                    "tags": ["security"],
                }
            ]
        )

        context = kb.build_prompt_context("where do visitors register")

        self.assertIn("[visitor-policy] Visitor policy", context)
        self.assertIn("Visitors must register at the main office", context)

    def test_load_sample_knowledge_base(self) -> None:
        kb = load_school_knowledge_base(Path("config/school_knowledge_base.yaml"))

        self.assertGreaterEqual(len(kb.documents), 5)

    def test_loads_markdown_knowledge_documents_from_configured_directory(self) -> None:
        with patch.dict(
            "os.environ",
            {"SCHOOL_KNOWLEDGE_MARKDOWN_DIR": "docs/school_kb"},
            clear=True,
        ):
            kb = load_school_knowledge_base(Path("config/school_knowledge_base.yaml"))

        results = kb.search("where do students take found items", limit=1)

        self.assertEqual(results[0].id, "lost-and-found")
        self.assertIn("front office", results[0].content)

    def test_load_defaults_to_fuzzy_school_knowledge_base(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            kb = load_school_knowledge_base(Path("config/school_knowledge_base.yaml"))

        self.assertIsInstance(kb, SchoolKnowledgeBase)

    def test_load_can_select_sqlite_vector_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.dict(
                    "os.environ",
                    {
                        "SCHOOL_KNOWLEDGE_BACKEND": "sqlite-vec",
                        "SCHOOL_VECTOR_DB_PATH": str(Path(temp_dir) / "school_vectors.db"),
                    },
                    clear=True,
                ),
                patch("src.school_knowledge_base.NvidiaEmbeddingProvider", return_value=FakeEmbedder()),
            ):
                kb = load_school_knowledge_base(Path("config/school_knowledge_base.yaml"))

            self.assertIsInstance(kb, SQLiteVectorKnowledgeBase)
            self.assertEqual(kb.search("visitor register", limit=1)[0].id, "visitor-policy")

    def test_load_can_select_faiss_backend(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.dict(
                    "os.environ",
                    {
                        "SCHOOL_KNOWLEDGE_BACKEND": "faiss",
                        "SCHOOL_FAISS_INDEX_PATH": str(Path(temp_dir) / "school.faiss"),
                    },
                    clear=True,
                ),
                patch("src.school_knowledge_base.NvidiaEmbeddingProvider", return_value=FakeEmbedder()),
            ):
                kb = load_school_knowledge_base(Path("config/school_knowledge_base.yaml"))

            self.assertIsInstance(kb, FAISSKnowledgeBase)
            self.assertEqual(kb.search("visitor register", limit=1)[0].id, "visitor-policy")


if __name__ == "__main__":
    unittest.main()
