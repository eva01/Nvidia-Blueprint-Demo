import json
import tempfile
import unittest
from pathlib import Path

from src.facility_ticket_marker import (
    FACILITY_TICKET_MARKER_PREFIX,
    create_ticket_from_marker,
    parse_ticket_marker,
)
from src.facility_tickets import FacilityTicketStore, TicketValidationError


class FacilityTicketMarkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = FacilityTicketStore(Path(self.temp_dir.name) / "tickets.db")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_ticket_marker_returns_ticket_payload(self) -> None:
        marker = _marker(
            {
                "category": "hvac",
                "location": "Classroom 3A",
                "summary": "Air conditioner is leaking near an electrical plug.",
                "urgency": "urgent",
                "reporter": "Ms Tan",
                "transcript_snippet": "The aircon in classroom 3A is leaking near a plug.",
            }
        )

        ticket = parse_ticket_marker(marker)

        self.assertEqual(ticket.category, "hvac")
        self.assertEqual(ticket.location, "Classroom 3A")
        self.assertEqual(ticket.summary, "Air conditioner is leaking near an electrical plug.")
        self.assertEqual(ticket.urgency, "urgent")
        self.assertEqual(ticket.reporter, "Ms Tan")
        self.assertEqual(ticket.transcript_snippet, "The aircon in classroom 3A is leaking near a plug.")

    def test_parse_ticket_marker_ignores_normal_spoken_text(self) -> None:
        self.assertIsNone(parse_ticket_marker("What room is the leak in?"))

    def test_parse_ticket_marker_rejects_missing_required_fields(self) -> None:
        marker = f'{FACILITY_TICKET_MARKER_PREFIX} {{"category":"hvac","location":"Classroom 3A"}}'

        with self.assertRaises(TicketValidationError):
            parse_ticket_marker(marker)

    def test_create_ticket_from_marker_persists_ticket_and_returns_spoken_confirmation(self) -> None:
        marker = _marker(
            {
                "category": "safety",
                "location": "Science stairwell",
                "summary": "Loose handrail on the second floor landing.",
                "urgency": "urgent",
                "reporter": "student monitor",
            }
        )

        result = create_ticket_from_marker(marker, self.store)

        self.assertIsNotNone(result)
        self.assertEqual(result.ticket.ticket_id, "FAC-000001")
        self.assertEqual(result.ticket.status, "open")
        self.assertEqual(
            result.speech_text,
            "Ticket FAC-000001 is created for an urgent safety issue in Science stairwell. "
            "Facilities can review it on the dashboard. Thank you. Goodbye.",
        )
        self.assertEqual(self.store.get_ticket("FAC-000001").summary, "Loose handrail on the second floor landing.")

    def test_create_ticket_from_marker_returns_none_for_non_marker_text(self) -> None:
        self.assertIsNone(create_ticket_from_marker("I need the reporter name first.", self.store))


def _marker(payload: dict[str, str]) -> str:
    return f"{FACILITY_TICKET_MARKER_PREFIX} {json.dumps(payload)}"


if __name__ == "__main__":
    unittest.main()
