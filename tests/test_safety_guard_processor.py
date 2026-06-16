import unittest

from pipecat.frames.frames import LLMFullResponseEndFrame, LLMFullResponseStartFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameDirection

from src.safety_guard_processor import SafetyGuardProcessor


class FakeSafetyGuard:
    def __init__(self, safe: bool) -> None:
        self.safe = safe
        self.checked = []

    def is_safe(self, text: str) -> bool:
        self.checked.append(text)
        return self.safe


class FailingSafetyGuard:
    def is_safe(self, text: str) -> bool:
        raise TimeoutError("safety model timed out")


class SafetyGuardProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def test_safe_response_passes_through(self) -> None:
        guard = FakeSafetyGuard(True)
        processor = SafetyGuardProcessor(guard)
        pushed = []

        async def capture(frame, direction):
            pushed.append((frame, direction))

        processor.push_frame = capture

        await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await processor.process_frame(
            LLMTextFrame("You can report that to the front office."),
            FrameDirection.DOWNSTREAM,
        )
        await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

        text_frames = [frame for frame, _ in pushed if isinstance(frame, LLMTextFrame)]
        self.assertEqual(text_frames[0].text, "You can report that to the front office.")
        self.assertEqual(guard.checked, ["You can report that to the front office."])

    async def test_unsafe_response_is_replaced(self) -> None:
        guard = FakeSafetyGuard(False)
        processor = SafetyGuardProcessor(guard, fallback_text="I cannot help with that request.")
        pushed = []

        async def capture(frame, direction):
            pushed.append((frame, direction))

        processor.push_frame = capture

        await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await processor.process_frame(LLMTextFrame("unsafe answer"), FrameDirection.DOWNSTREAM)
        await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

        text_frames = [frame for frame, _ in pushed if isinstance(frame, LLMTextFrame)]
        self.assertEqual(len(text_frames), 1)
        self.assertEqual(text_frames[0].text, "I cannot help with that request.")

    async def test_guard_failure_allows_response_to_keep_call_alive(self) -> None:
        processor = SafetyGuardProcessor(FailingSafetyGuard(), fallback_text="blocked")
        pushed = []

        async def capture(frame, direction):
            pushed.append((frame, direction))

        processor.push_frame = capture

        await processor.process_frame(LLMFullResponseStartFrame(), FrameDirection.DOWNSTREAM)
        await processor.process_frame(LLMTextFrame("What is the reporter's name?"), FrameDirection.DOWNSTREAM)
        await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

        text_frames = [frame for frame, _ in pushed if isinstance(frame, LLMTextFrame)]
        self.assertEqual(len(text_frames), 1)
        self.assertEqual(text_frames[0].text, "What is the reporter's name?")


if __name__ == "__main__":
    unittest.main()
