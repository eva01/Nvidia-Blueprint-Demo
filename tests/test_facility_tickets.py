import tempfile
import unittest
import warnings
from pathlib import Path

from src.facility_sovereignty import FacilitySovereigntyPolicy
from src.facility_tickets import FacilityTicketStore, TicketCreate, TicketUpdate, TicketValidationError


class FacilityTicketStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "facility_tickets.db"
        self.store = FacilityTicketStore(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_create_ticket_assigns_sequential_facility_id_and_defaults_to_open(self) -> None:
        first = self.store.create_ticket(
            TicketCreate(
                category="hvac",
                location="Classroom 3A",
                summary="Air conditioner is leaking near the teacher desk.",
                urgency="urgent",
                reporter="Ms Tan",
                transcript_snippet="The aircon in classroom 3A is leaking near a plug.",
            )
        )
        second = self.store.create_ticket(
            TicketCreate(
                category="it",
                location="Library counter",
                summary="Self checkout terminal is not responding.",
                urgency="normal",
                reporter="librarian",
            )
        )

        self.assertEqual(first.ticket_id, "FAC-000001")
        self.assertEqual(second.ticket_id, "FAC-000002")
        self.assertEqual(first.status, "open")
        self.assertEqual(first.category, "hvac")
        self.assertEqual(first.location, "Classroom 3A")
        self.assertEqual(first.urgency, "urgent")
        self.assertEqual(first.reporter, "Ms Tan")
        self.assertEqual(first.sensitivity, "standard")
        self.assertFalse(first.redaction_applied)
        self.assertTrue(first.created_at.endswith("Z"))
        self.assertTrue(first.updated_at.endswith("Z"))

    def test_create_ticket_preserves_contact_details_by_default(self) -> None:
        created = self.store.create_ticket(
            TicketCreate(
                category="it",
                location="Library counter",
                summary="Parent email parent@example.edu and phone 555-123-4567 need follow up.",
                urgency="normal",
                reporter="office",
                transcript_snippet="Student ID S1234567A reported this from parent@example.edu.",
            )
        )

        self.assertEqual(created.sensitivity, "standard")
        self.assertFalse(created.redaction_applied)
        self.assertIn("parent@example.edu", created.summary)
        self.assertIn("555-123-4567", created.summary)
        self.assertIn("S1234567A", created.transcript_snippet)

    def test_create_ticket_redacts_common_pii_when_explicitly_enabled(self) -> None:
        redacting_store = FacilityTicketStore(
            self.db_path,
            policy=FacilitySovereigntyPolicy(pii_redaction_enabled=True),
        )

        created = redacting_store.create_ticket(
            TicketCreate(
                category="it",
                location="Library counter",
                summary="Parent email parent@example.edu and phone 555-123-4567 need follow up.",
                urgency="normal",
                reporter="office",
                transcript_snippet="Student ID S1234567A reported this from parent@example.edu.",
            )
        )

        self.assertEqual(created.sensitivity, "redacted")
        self.assertTrue(created.redaction_applied)
        self.assertIn("[REDACTED_EMAIL]", created.summary)
        self.assertIn("[REDACTED_PHONE]", created.summary)
        self.assertIn("[REDACTED_STUDENT_ID]", created.transcript_snippet)

    def test_list_tickets_returns_created_records_in_id_order(self) -> None:
        self.store.create_ticket(
            TicketCreate(
                category="cleaning",
                location="Cafeteria",
                summary="Spill beside the tray return area.",
                urgency="normal",
                reporter="canteen staff",
            )
        )
        self.store.create_ticket(
            TicketCreate(
                category="safety",
                location="Science block stairwell",
                summary="Loose handrail on the second floor landing.",
                urgency="urgent",
                reporter="student monitor",
            )
        )

        tickets = self.store.list_tickets()

        self.assertEqual([ticket.ticket_id for ticket in tickets], ["FAC-000001", "FAC-000002"])
        self.assertEqual(tickets[1].category, "safety")

    def test_get_ticket_returns_record_or_none(self) -> None:
        created = self.store.create_ticket(
            TicketCreate(
                category="plumbing",
                location="Block B restroom",
                summary="Sink tap is stuck open.",
                urgency="urgent",
                reporter="office",
            )
        )

        found = self.store.get_ticket(created.ticket_id)

        self.assertIsNotNone(found)
        self.assertEqual(found.ticket_id, created.ticket_id)
        self.assertIsNone(self.store.get_ticket("FAC-999999"))

    def test_update_status_persists_allowed_status(self) -> None:
        created = self.store.create_ticket(
            TicketCreate(
                category="furniture",
                location="Room 2B",
                summary="Broken chair at the back row.",
                urgency="low",
                reporter="teacher aide",
            )
        )

        updated = self.store.update_status(created.ticket_id, "in_progress")

        self.assertEqual(updated.status, "in_progress")
        self.assertGreaterEqual(updated.updated_at, created.updated_at)
        self.assertEqual(self.store.get_ticket(created.ticket_id).status, "in_progress")

    def test_update_ticket_persists_editable_fields_and_audit_event(self) -> None:
        created = self.store.create_ticket(
            TicketCreate(
                category="other",
                location="Old room",
                summary="Original summary.",
                urgency="normal",
                reporter="office",
                transcript_snippet="Original notes.",
            )
        )

        updated = self.store.update_ticket(
            created.ticket_id,
            TicketUpdate(
                status="in_progress",
                category="safety",
                location="Science lab 2",
                summary="Water near an outlet.",
                urgency="urgent",
                reporter="Jin",
                transcript_snippet="Reporter said water is near the outlet.",
            ),
        )

        self.assertEqual(updated.status, "in_progress")
        self.assertEqual(updated.category, "safety")
        self.assertEqual(updated.location, "Science lab 2")
        self.assertEqual(updated.summary, "Water near an outlet.")
        self.assertEqual(updated.urgency, "urgent")
        self.assertEqual(updated.reporter, "Jin")
        self.assertEqual(updated.transcript_snippet, "Reporter said water is near the outlet.")
        self.assertEqual(self.store.get_ticket(created.ticket_id).summary, "Water near an outlet.")
        events = self.store.list_audit_events()
        self.assertEqual(events[-1].event_type, "ticket_updated")
        self.assertEqual(
            events[-1].details["fields"],
            ["category", "location", "reporter", "status", "summary", "transcript_snippet", "urgency"],
        )

    def test_delete_ticket_removes_record_and_records_audit_event(self) -> None:
        created = self.store.create_ticket(
            TicketCreate(
                category="cleaning",
                location="Cafeteria",
                summary="Spill near tray return.",
                urgency="normal",
                reporter="staff",
            )
        )

        deleted = self.store.delete_ticket(created.ticket_id)

        self.assertEqual(deleted.ticket_id, created.ticket_id)
        self.assertIsNone(self.store.get_ticket(created.ticket_id))
        events = self.store.list_audit_events()
        self.assertEqual(events[-1].event_type, "ticket_deleted")
        self.assertEqual(events[-1].ticket_id, created.ticket_id)

    def test_audit_events_record_ticket_lifecycle_without_transcript(self) -> None:
        created = self.store.create_ticket(
            TicketCreate(
                category="safety",
                location="Gym",
                summary="Exit sign is flickering.",
                urgency="urgent",
                reporter="coach@example.edu",
                transcript_snippet="Reporter phone 555-987-1234.",
            )
        )
        self.store.update_status(created.ticket_id, "resolved")

        events = self.store.list_audit_events()

        self.assertEqual([event.event_type for event in events], ["ticket_created", "ticket_status_updated"])
        self.assertEqual(events[0].ticket_id, created.ticket_id)
        self.assertEqual(events[0].actor, "voice_agent")
        self.assertEqual(events[0].details["category"], "safety")
        self.assertEqual(events[0].details["redaction_applied"], False)
        self.assertNotIn("transcript", events[0].details)
        self.assertEqual(events[1].details["status"], "resolved")

    def test_summary_aggregates_counts_without_raw_ticket_text(self) -> None:
        self.store.create_ticket(
            TicketCreate(
                category="it",
                location="Library counter",
                summary="Parent email parent@example.edu needs account reset.",
                urgency="normal",
                reporter="office",
                transcript_snippet="Student ID S1234567A reported this.",
            )
        )
        second = self.store.create_ticket(
            TicketCreate(
                category="safety",
                location="Gym",
                summary="Exit sign is flickering.",
                urgency="urgent",
                reporter="coach",
            )
        )
        self.store.update_status(second.ticket_id, "in_progress")

        summary = self.store.get_summary()

        self.assertEqual(summary["total_tickets"], 2)
        self.assertEqual(summary["open_tickets"], 1)
        self.assertEqual(summary["status_counts"], {"in_progress": 1, "open": 1, "resolved": 0})
        self.assertEqual(summary["category_counts"], {"it": 1, "safety": 1})
        self.assertEqual(summary["urgency_counts"], {"normal": 1, "urgent": 1})
        self.assertEqual(summary["redacted_tickets"], 0)
        self.assertEqual(summary["audit_events"], 3)
        self.assertEqual(summary["last_ticket_id"], second.ticket_id)
        self.assertNotIn("parent@example.edu", str(summary))
        self.assertNotIn("S1234567A", str(summary))
        self.assertNotIn("Exit sign", str(summary))

    def test_existing_ticket_table_is_migrated_for_sovereign_columns(self) -> None:
        import sqlite3

        legacy_db = Path(self.temp_dir.name) / "legacy.db"
        conn = sqlite3.connect(legacy_db)
        with conn:
            conn.execute(
                """
                CREATE TABLE facility_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    category TEXT NOT NULL,
                    location TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    reporter TEXT NOT NULL,
                    transcript_snippet TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        conn.close()

        store = FacilityTicketStore(legacy_db)
        created = store.create_ticket(
            TicketCreate(
                category="cleaning",
                location="Cafeteria",
                summary="Spill near tray return.",
                urgency="normal",
                reporter="staff",
            )
        )

        self.assertEqual(created.ticket_id, "FAC-000001")
        self.assertEqual(created.sensitivity, "standard")
        self.assertEqual(store.list_audit_events()[0].event_type, "ticket_created")

    def test_update_status_rejects_unknown_ticket(self) -> None:
        with self.assertRaises(KeyError):
            self.store.update_status("FAC-999999", "resolved")

    def test_rejects_invalid_enums_and_blank_required_fields(self) -> None:
        invalid_inputs = [
            TicketCreate(
                category="gardening",
                location="Courtyard",
                summary="Tree branch blocking walkway.",
                urgency="normal",
                reporter="guard",
            ),
            TicketCreate(
                category="other",
                location="",
                summary="Door is difficult to close.",
                urgency="normal",
                reporter="office",
            ),
            TicketCreate(
                category="other",
                location="Main office",
                summary="",
                urgency="normal",
                reporter="office",
            ),
            TicketCreate(
                category="other",
                location="Main office",
                summary="Door is difficult to close.",
                urgency="critical",
                reporter="office",
            ),
        ]

        for ticket in invalid_inputs:
            with self.subTest(ticket=ticket), self.assertRaises(TicketValidationError):
                self.store.create_ticket(ticket)

    def test_store_closes_sqlite_connections(self) -> None:
        import gc

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "facility_tickets.db"

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ResourceWarning)
                store = FacilityTicketStore(db_path)
                created = store.create_ticket(
                    TicketCreate(
                        category="hvac",
                        location="Classroom 4B",
                        summary="Vent is rattling during lessons.",
                        urgency="normal",
                        reporter="Ms Lim",
                    )
                )
                store.list_tickets()
                store.get_ticket(created.ticket_id)
                store.update_status(created.ticket_id, "resolved")
                del store
                gc.collect()

            resource_warnings = [warning for warning in caught if issubclass(warning.category, ResourceWarning)]
            self.assertEqual([], resource_warnings)


if __name__ == "__main__":
    unittest.main()
