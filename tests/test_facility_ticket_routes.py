import asyncio
import os
import tempfile
import unittest
from pathlib import Path

from src import facility_ticket_routes
from src.facility_ticket_routes import (
    TicketCreateRequest,
    TicketStatusRequest,
    TicketUpdateRequest,
    create_facility_ticket,
    delete_facility_ticket,
    get_facility_sovereignty_status,
    get_facility_summary,
    list_facility_audit_events,
    search_school_knowledge,
    update_facility_ticket,
    update_facility_ticket_status,
)


class FacilityTicketRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "facility_tickets.db"
        self.original_env = dict(os.environ)
        os.environ.update(
            {
                "FACILITY_TICKETS_DB_PATH": str(self.db_path),
                "SCHOOL_KNOWLEDGE_BASE_PATH": str(Path.cwd() / "config" / "school_knowledge_base.yaml"),
                "SOVEREIGN_MODE": "local-demo",
                "DATA_RESIDENCY_REGION": "school-lab",
                "ALLOW_CLOUD_NIM": "true",
                "PII_REDACTION_ENABLED": "false",
                "AUDIT_LOG_ENABLED": "true",
                "ASR_SERVER_URL": "grpc.nvcf.nvidia.com:443",
                "TTS_SERVER_URL": "grpc.nvcf.nvidia.com:443",
                "NVIDIA_LLM_URL": "https://integrate.api.nvidia.com/v1",
                "NVIDIA_API_KEY": "test-key",
            }
        )
        facility_ticket_routes._store = None

    def tearDown(self) -> None:
        facility_ticket_routes._store = None
        os.environ.clear()
        os.environ.update(self.original_env)
        self.temp_dir.cleanup()

    def test_sovereignty_status_is_secret_safe(self) -> None:
        status = asyncio.run(get_facility_sovereignty_status())

        self.assertEqual(status["mode"], "local-demo")
        self.assertEqual(status["data_residency_region"], "school-lab")
        self.assertEqual(status["storage_backend"], "sqlite-local")
        self.assertEqual(status["database_path"], str(self.db_path.resolve()))
        self.assertEqual(status["asr_endpoint_type"], "cloud_nim")
        self.assertTrue(status["api_key_configured"])
        self.assertNotIn("test-key", str(status))

    def test_audit_route_lists_create_and_status_events(self) -> None:
        created = asyncio.run(
            create_facility_ticket(
                TicketCreateRequest(
                    category="hvac",
                    location="Classroom 3A",
                    summary="Email parent@example.edu about the leaking vent.",
                    urgency="urgent",
                    reporter="office",
                )
            )
        )
        asyncio.run(update_facility_ticket_status(created["ticket_id"], TicketStatusRequest(status="in_progress")))

        events = asyncio.run(list_facility_audit_events())

        self.assertEqual([event["event_type"] for event in events], ["ticket_created", "ticket_status_updated"])
        self.assertEqual(events[0]["ticket_id"], created["ticket_id"])
        self.assertEqual(events[0]["details"]["redaction_applied"], False)

    def test_update_and_delete_ticket_routes(self) -> None:
        created = asyncio.run(
            create_facility_ticket(
                TicketCreateRequest(
                    category="other",
                    location="Old room",
                    summary="Original summary.",
                    urgency="normal",
                    reporter="office",
                )
            )
        )

        updated = asyncio.run(
            update_facility_ticket(
                created["ticket_id"],
                TicketUpdateRequest(
                    status="in_progress",
                    category="safety",
                    location="Science lab 2",
                    summary="Water near an outlet.",
                    urgency="urgent",
                    reporter="Jin",
                    transcript_snippet="Reporter said water is near the outlet.",
                ),
            )
        )
        deleted = asyncio.run(delete_facility_ticket(created["ticket_id"]))
        events = asyncio.run(list_facility_audit_events())

        self.assertEqual(updated["status"], "in_progress")
        self.assertEqual(updated["category"], "safety")
        self.assertEqual(updated["location"], "Science lab 2")
        self.assertEqual(deleted["ticket_id"], created["ticket_id"])
        self.assertEqual(deleted["deleted"], True)
        self.assertEqual(
            [event["event_type"] for event in events],
            ["ticket_created", "ticket_updated", "ticket_deleted"],
        )

    def test_summary_route_is_secret_safe_and_includes_sovereignty(self) -> None:
        created = asyncio.run(
            create_facility_ticket(
                TicketCreateRequest(
                    category="it",
                    location="Library counter",
                    summary="Email parent@example.edu about account access.",
                    urgency="urgent",
                    reporter="office",
                    transcript_snippet="Student ID S1234567A requested help.",
                )
            )
        )
        asyncio.run(update_facility_ticket_status(created["ticket_id"], TicketStatusRequest(status="resolved")))

        summary = asyncio.run(get_facility_summary())

        self.assertEqual(summary["total_tickets"], 1)
        self.assertEqual(summary["open_tickets"], 0)
        self.assertEqual(summary["status_counts"]["resolved"], 1)
        self.assertEqual(summary["category_counts"], {"it": 1})
        self.assertEqual(summary["urgency_counts"], {"urgent": 1})
        self.assertEqual(summary["redacted_tickets"], 0)
        self.assertEqual(summary["audit_events"], 2)
        self.assertEqual(summary["last_ticket_id"], created["ticket_id"])
        self.assertEqual(summary["sovereignty"]["mode"], "local-demo")
        self.assertEqual(summary["sovereignty"]["data_residency_region"], "school-lab")
        self.assertEqual(summary["sovereignty"]["storage_backend"], "sqlite-local")
        self.assertNotIn("parent@example.edu", str(summary))
        self.assertNotIn("S1234567A", str(summary))
        self.assertNotIn("account access", str(summary))

    def test_knowledge_search_returns_local_school_procedures(self) -> None:
        results = asyncio.run(search_school_knowledge("where do visitors register"))

        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "visitor-policy")
        self.assertIn("main office", results[0]["content"])


if __name__ == "__main__":
    unittest.main()
