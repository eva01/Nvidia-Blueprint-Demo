import json
import tempfile
import unittest
from pathlib import Path

from pipecat.frames.frames import LLMFullResponseEndFrame, LLMTextFrame
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi import RTVIServerMessageFrame

from src.facility_ticket_marker import FACILITY_TICKET_MARKER_PREFIX
from src.facility_ticket_processor import FacilityTicketMarkerProcessor
from src.facility_tickets import FacilityTicketStore


class FacilityTicketMarkerProcessorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = FacilityTicketStore(Path(self.temp_dir.name) / "tickets.db")

    async def asyncTearDown(self) -> None:
        self.temp_dir.cleanup()

    async def test_ticket_marker_emits_confirmation_and_stop_control_event(self) -> None:
        processor = FacilityTicketMarkerProcessor(self.store)
        pushed = []

        async def capture(frame, direction):
            pushed.append((frame, direction))

        processor.push_frame = capture
        marker = f"{FACILITY_TICKET_MARKER_PREFIX} " + json.dumps(
            {
                "category": "safety",
                "location": "Science lab 2",
                "summary": "Water near an outlet.",
                "urgency": "urgent",
                "reporter": "Jin demo",
            }
        )

        await processor.process_frame(LLMTextFrame(marker), FrameDirection.DOWNSTREAM)
        await processor.process_frame(LLMFullResponseEndFrame(), FrameDirection.DOWNSTREAM)

        text_frames = [frame for frame, _ in pushed if isinstance(frame, LLMTextFrame)]
        control_frames = [frame for frame, _ in pushed if isinstance(frame, RTVIServerMessageFrame)]

        self.assertEqual(len(text_frames), 1)
        self.assertIn("Ticket FAC-000001 is created", text_frames[0].text)
        self.assertIn("Facilities can review it on the dashboard", text_frames[0].text)
        self.assertTrue(text_frames[0].text.endswith("Thank you. Goodbye."))
        self.assertEqual(len(control_frames), 1)
        self.assertEqual(
            control_frames[0].data,
            {
                "type": "facility_ticket_created",
                "ticket_id": "FAC-000001",
                "status": "open",
                "category": "safety",
                "urgency": "urgent",
            },
        )


if __name__ == "__main__":
    unittest.main()
