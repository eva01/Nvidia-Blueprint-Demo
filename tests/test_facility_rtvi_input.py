import types
import unittest
from pathlib import Path

from src.facility_rtvi import FacilityRTVIInput


class FakeContext:
    def __init__(self):
        self.messages = [{"role": "user", "content": "system prompt"}]

    def get_messages(self):
        return self.messages


class FacilityRTVIInputTests(unittest.IsolatedAsyncioTestCase):
    async def test_submit_user_text_pushes_llm_update(self):
        processor = object.__new__(FacilityRTVIInput)
        processor._context = FakeContext()
        processor.pushed = []
        processor.responses = []
        processor.errors = []

        async def push_frame(self, frame):
            self.pushed.append(frame)

        async def send_server_response(self, msg, payload):
            self.responses.append(payload)

        async def send_error_response(self, msg, error):
            self.errors.append(error)

        processor.push_frame = types.MethodType(push_frame, processor)
        processor.send_server_response = types.MethodType(send_server_response, processor)
        processor.send_error_response = types.MethodType(send_error_response, processor)

        await processor._handle_submit_user_text(object(), {"text": "Category is electrical."})

        self.assertEqual([], processor.errors)
        self.assertEqual([{"status": "submitted"}], processor.responses)
        self.assertEqual("Category is electrical.", processor.pushed[0].messages[-1]["content"])
        self.assertTrue(processor.pushed[0].run_llm)

    async def test_submit_user_text_rejects_blank_text(self):
        processor = object.__new__(FacilityRTVIInput)
        processor._context = FakeContext()
        processor.errors = []

        async def send_error_response(self, msg, error):
            self.errors.append(error)

        processor.send_error_response = types.MethodType(send_error_response, processor)

        await processor._handle_submit_user_text(object(), {"text": "   "})

        self.assertEqual(["Missing text"], processor.errors)

    def test_pipeline_uses_facility_rtvi_input(self):
        pipeline_source = (Path(__file__).resolve().parents[1] / "src" / "pipeline.py").read_text(encoding="utf-8")

        self.assertIn("from src.facility_rtvi import FacilityRTVIInput", pipeline_source)
        self.assertIn("rtvi_input = FacilityRTVIInput(", pipeline_source)
        self.assertNotIn("rtvi_input = NvidiaRTVIInput(", pipeline_source)
