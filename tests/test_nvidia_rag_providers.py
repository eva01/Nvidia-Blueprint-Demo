import json
import unittest

from src.nvidia_rag_providers import NvidiaEmbeddingProvider, NvidiaRerankProvider, NvidiaSafetyGuardProvider
from src.school_knowledge_base import KnowledgeDocument


class NvidiaRAGProviderTests(unittest.TestCase):
    def test_embedding_provider_posts_openai_compatible_payload(self) -> None:
        calls = []

        def post_json(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"data": [{"embedding": [0.1, 0.2]}, {"embedding": [0.3, 0.4]}]}

        provider = NvidiaEmbeddingProvider(
            api_key="test-key",
            base_url="https://integrate.api.nvidia.com/v1",
            model="nvidia/test-embed",
            post_json=post_json,
            timeout=9,
        )

        vectors = provider.embed(["one", "two"])

        self.assertEqual(vectors, [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(calls[0][0], "https://integrate.api.nvidia.com/v1/embeddings")
        self.assertEqual(calls[0][1]["Authorization"], "Bearer test-key")
        self.assertEqual(calls[0][2], {"model": "nvidia/test-embed", "input": ["one", "two"]})
        self.assertEqual(calls[0][3], 9)

    def test_embedding_provider_sends_input_type_for_documents_and_queries(self) -> None:
        payloads = []

        def post_json(url, headers, payload, timeout):
            payloads.append(payload)
            return {"data": [{"embedding": [0.1, 0.2]}]}

        provider = NvidiaEmbeddingProvider(api_key="test-key", model="nvidia/test-embed", post_json=post_json)

        provider.embed_documents(["policy chunk"])
        provider.embed_query("policy question")

        self.assertEqual(payloads[0]["input_type"], "passage")
        self.assertEqual(payloads[1]["input_type"], "query")

    def test_rerank_provider_orders_documents_from_scores(self) -> None:
        def post_json(url, headers, payload, timeout):
            return json.loads(
                """
                {
                  "rankings": [
                    {"index": 1, "logit": 0.9},
                    {"index": 0, "logit": 0.2}
                  ]
                }
                """
            )

        provider = NvidiaRerankProvider(
            api_key="test-key",
            base_url="https://ai.api.nvidia.com/v1/retrieval/nvidia/test-rerank/reranking",
            model="nvidia/test-rerank",
            post_json=post_json,
        )
        documents = [
            KnowledgeDocument(id="a", title="A", content="alpha", tags=()),
            KnowledgeDocument(id="b", title="B", content="beta", tags=()),
        ]

        ranked = provider.rerank("question", documents, limit=2)

        self.assertEqual([document.id for document in ranked], ["b", "a"])

    def test_safety_guard_provider_parses_safe_and_unsafe_responses(self) -> None:
        responses = [
            {"choices": [{"message": {"content": "safe"}}]},
            {"choices": [{"message": {"content": "unsafe"}}]},
        ]

        def post_json(url, headers, payload, timeout):
            return responses.pop(0)

        provider = NvidiaSafetyGuardProvider(api_key="test-key", model="nvidia/test-safety", post_json=post_json)

        self.assertTrue(provider.is_safe("ordinary school support answer"))
        self.assertFalse(provider.is_safe("unsafe answer"))


if __name__ == "__main__":
    unittest.main()
