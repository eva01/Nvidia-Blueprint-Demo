import unittest

from pipecat.frames.frames import LLMMessagesAppendFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection

from src.school_knowledge_base import SchoolKnowledgeBase
from src.school_rag_processor import SchoolRAGContextProcessor


class SchoolRAGContextProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_final_transcript_injects_retrieved_context_before_user_text(self) -> None:
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
        processor = SchoolRAGContextProcessor(kb, min_score=1)
        pushed = []

        async def capture(frame, direction):
            pushed.append((frame, direction))

        processor.push_frame = capture

        await processor.process_frame(
            TranscriptionFrame("where should visitors register", "user", "2026-06-22T00:00:00Z"),
            FrameDirection.DOWNSTREAM,
        )

        self.assertIsInstance(pushed[0][0], LLMMessagesAppendFrame)
        self.assertIn("visitor-policy", pushed[0][0].messages[0]["content"])
        self.assertIsInstance(pushed[1][0], TranscriptionFrame)

    async def test_ticket_intake_questions_do_not_inject_knowledge_context(self) -> None:
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
        processor = SchoolRAGContextProcessor(kb, min_score=1)
        pushed = []

        async def capture(frame, direction):
            pushed.append((frame, direction))

        processor.push_frame = capture

        await processor.process_frame(
            TranscriptionFrame("i need to report broken air conditioner", "user", "2026-06-22T00:00:00Z"),
            FrameDirection.DOWNSTREAM,
        )

        self.assertEqual(len(pushed), 1)
        self.assertIsInstance(pushed[0][0], TranscriptionFrame)


if __name__ == "__main__":
    unittest.main()
