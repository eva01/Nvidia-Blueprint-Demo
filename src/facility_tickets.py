# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""SQLite-backed school facility ticket storage."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from src.facility_sovereignty import FacilitySovereigntyPolicy, load_facility_sovereignty_policy

ALLOWED_CATEGORIES = {
    "hvac",
    "electrical",
    "plumbing",
    "it",
    "furniture",
    "safety",
    "cleaning",
    "other",
}
ALLOWED_STATUSES = {"open", "in_progress", "resolved"}
ALLOWED_URGENCIES = {"low", "normal", "urgent"}


class TicketValidationError(ValueError):
    """Raised when a facility ticket payload fails validation."""


@dataclass(frozen=True)
class TicketCreate:
    """Facility ticket creation payload."""

    category: str
    location: str
    summary: str
    urgency: str = "normal"
    reporter: str = "unknown"
    transcript_snippet: str = ""


@dataclass(frozen=True)
class TicketUpdate:
    """Facility ticket update payload."""

    status: str | None = None
    category: str | None = None
    location: str | None = None
    summary: str | None = None
    urgency: str | None = None
    reporter: str | None = None
    transcript_snippet: str | None = None


@dataclass(frozen=True)
class _NormalizedTicketUpdate:
    status: str
    category: str
    location: str
    summary: str
    urgency: str
    reporter: str
    transcript_snippet: str


@dataclass(frozen=True)
class TicketRecord:
    """Facility ticket record returned from storage."""

    ticket_id: str
    status: str
    category: str
    location: str
    summary: str
    urgency: str
    reporter: str
    transcript_snippet: str
    sensitivity: str
    redaction_applied: bool
    created_at: str
    updated_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


@dataclass(frozen=True)
class AuditEventRecord:
    """Audit event record returned from storage."""

    event_id: str
    event_type: str
    ticket_id: str
    actor: str
    details: dict[str, object]
    created_at: str

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


class FacilityTicketStore:
    """Persists school facility support tickets in SQLite."""

    def __init__(self, db_path: str | Path, policy: FacilitySovereigntyPolicy | None = None) -> None:
        self.db_path = Path(db_path)
        self.policy = policy or load_facility_sovereignty_policy()
        self._ensure_schema()

    def create_ticket(self, ticket: TicketCreate) -> TicketRecord:
        """Validate and create a ticket."""
        normalized = self._validate_create(ticket)
        normalized, redaction_applied = self._redact_ticket(normalized)
        sensitivity = "redacted" if redaction_applied else "standard"
        now = _utc_now()
        pending_ticket_id = f"__pending__{uuid.uuid4()}"

        with self._connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO facility_tickets (
                    ticket_id,
                    status,
                    category,
                    location,
                    summary,
                    urgency,
                    reporter,
                    transcript_snippet,
                    sensitivity,
                    redaction_applied,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pending_ticket_id,
                    "open",
                    normalized.category,
                    normalized.location,
                    normalized.summary,
                    normalized.urgency,
                    normalized.reporter,
                    normalized.transcript_snippet,
                    sensitivity,
                    int(redaction_applied),
                    now,
                    now,
                ),
            )
            row_id = cursor.lastrowid
            ticket_id = f"FAC-{row_id:06d}"
            conn.execute(
                "UPDATE facility_tickets SET ticket_id = ? WHERE id = ?",
                (ticket_id, row_id),
            )
            self._insert_audit_event(
                conn,
                event_type="ticket_created",
                ticket_id=ticket_id,
                actor="voice_agent",
                details={
                    "category": normalized.category,
                    "urgency": normalized.urgency,
                    "status": "open",
                    "sensitivity": sensitivity,
                    "redaction_applied": redaction_applied,
                },
                created_at=now,
            )

        created = self.get_ticket(ticket_id)
        if created is None:
            raise RuntimeError(f"Created ticket {ticket_id} could not be read back")
        return created

    def list_tickets(self) -> list[TicketRecord]:
        """Return all tickets in creation order."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT ticket_id, status, category, location, summary, urgency,
                       reporter, transcript_snippet, sensitivity, redaction_applied,
                       created_at, updated_at
                FROM facility_tickets
                ORDER BY id ASC
                """
            ).fetchall()
        return [_record_from_row(row) for row in rows]

    def get_ticket(self, ticket_id: str) -> TicketRecord | None:
        """Return a ticket by ID, or None when it does not exist."""
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT ticket_id, status, category, location, summary, urgency,
                       reporter, transcript_snippet, sensitivity, redaction_applied,
                       created_at, updated_at
                FROM facility_tickets
                WHERE ticket_id = ?
                """,
                (ticket_id,),
            ).fetchone()
        return _record_from_row(row) if row else None

    def update_status(self, ticket_id: str, status: str) -> TicketRecord:
        """Update a ticket status and return the updated record."""
        normalized_status = status.strip().lower()
        if normalized_status not in ALLOWED_STATUSES:
            raise TicketValidationError(f"status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")

        now = _utc_now()
        with self._connection() as conn:
            existing = conn.execute(
                "SELECT status FROM facility_tickets WHERE ticket_id = ?",
                (ticket_id,),
            ).fetchone()
            if existing is None:
                raise KeyError(ticket_id)
            cursor = conn.execute(
                "UPDATE facility_tickets SET status = ?, updated_at = ? WHERE ticket_id = ?",
                (normalized_status, now, ticket_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(ticket_id)
            self._insert_audit_event(
                conn,
                event_type="ticket_status_updated",
                ticket_id=ticket_id,
                actor="operator",
                details={
                    "from_status": existing["status"],
                    "status": normalized_status,
                },
                created_at=now,
            )

        updated = self.get_ticket(ticket_id)
        if updated is None:
            raise KeyError(ticket_id)
        return updated

    def update_ticket(self, ticket_id: str, update: TicketUpdate) -> TicketRecord:
        """Update editable ticket fields and return the updated record."""
        existing = self.get_ticket(ticket_id)
        if existing is None:
            raise KeyError(ticket_id)

        normalized = self._validate_update(update, existing)
        redacted_ticket, redaction_applied = self._redact_ticket(
            TicketCreate(
                category=normalized.category,
                location=normalized.location,
                summary=normalized.summary,
                urgency=normalized.urgency,
                reporter=normalized.reporter,
                transcript_snippet=normalized.transcript_snippet,
            )
        )
        final_redaction_applied = redaction_applied or existing.redaction_applied
        sensitivity = "redacted" if final_redaction_applied else existing.sensitivity
        normalized = _NormalizedTicketUpdate(
            status=normalized.status,
            category=redacted_ticket.category,
            location=redacted_ticket.location,
            summary=redacted_ticket.summary,
            urgency=redacted_ticket.urgency,
            reporter=redacted_ticket.reporter,
            transcript_snippet=redacted_ticket.transcript_snippet,
        )
        fields = _changed_fields(existing, normalized, sensitivity, final_redaction_applied)
        now = _utc_now()

        with self._connection() as conn:
            cursor = conn.execute(
                """
                UPDATE facility_tickets
                SET status = ?,
                    category = ?,
                    location = ?,
                    summary = ?,
                    urgency = ?,
                    reporter = ?,
                    transcript_snippet = ?,
                    sensitivity = ?,
                    redaction_applied = ?,
                    updated_at = ?
                WHERE ticket_id = ?
                """,
                (
                    normalized.status,
                    normalized.category,
                    normalized.location,
                    normalized.summary,
                    normalized.urgency,
                    normalized.reporter,
                    normalized.transcript_snippet,
                    sensitivity,
                    int(final_redaction_applied),
                    now,
                    ticket_id,
                ),
            )
            if cursor.rowcount == 0:
                raise KeyError(ticket_id)
            self._insert_audit_event(
                conn,
                event_type="ticket_updated",
                ticket_id=ticket_id,
                actor="operator",
                details={
                    "fields": fields,
                    "status": normalized.status,
                    "category": normalized.category,
                    "urgency": normalized.urgency,
                    "redaction_applied": final_redaction_applied,
                },
                created_at=now,
            )

        updated = self.get_ticket(ticket_id)
        if updated is None:
            raise KeyError(ticket_id)
        return updated

    def delete_ticket(self, ticket_id: str) -> TicketRecord:
        """Delete a ticket and return the deleted record."""
        existing = self.get_ticket(ticket_id)
        if existing is None:
            raise KeyError(ticket_id)

        now = _utc_now()
        with self._connection() as conn:
            self._insert_audit_event(
                conn,
                event_type="ticket_deleted",
                ticket_id=ticket_id,
                actor="operator",
                details={
                    "status": existing.status,
                    "category": existing.category,
                    "urgency": existing.urgency,
                },
                created_at=now,
            )
            cursor = conn.execute("DELETE FROM facility_tickets WHERE ticket_id = ?", (ticket_id,))
            if cursor.rowcount == 0:
                raise KeyError(ticket_id)

        return existing

    def list_audit_events(self) -> list[AuditEventRecord]:
        """Return audit events in creation order."""
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, event_type, ticket_id, actor, details_json, created_at
                FROM facility_audit_events
                ORDER BY id ASC
                """
            ).fetchall()
        return [_audit_event_from_row(row) for row in rows]

    def get_summary(self) -> dict[str, object]:
        """Return aggregate operator metrics without raw ticket text."""
        with self._connection() as conn:
            total_tickets = _count(conn, "SELECT COUNT(*) FROM facility_tickets")
            open_tickets = _count(conn, "SELECT COUNT(*) FROM facility_tickets WHERE status = 'open'")
            redacted_tickets = _count(conn, "SELECT COUNT(*) FROM facility_tickets WHERE redaction_applied = 1")
            audit_events = _count(conn, "SELECT COUNT(*) FROM facility_audit_events")
            last_ticket = conn.execute("SELECT ticket_id FROM facility_tickets ORDER BY id DESC LIMIT 1").fetchone()
            return {
                "total_tickets": total_tickets,
                "open_tickets": open_tickets,
                "status_counts": _counts_by_value(conn, "status", ALLOWED_STATUSES),
                "category_counts": _counts_by_value(conn, "category"),
                "urgency_counts": _counts_by_value(conn, "urgency"),
                "redacted_tickets": redacted_tickets,
                "audit_events": audit_events,
                "last_ticket_id": last_ticket["ticket_id"] if last_ticket else None,
            }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facility_tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticket_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    category TEXT NOT NULL,
                    location TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    urgency TEXT NOT NULL,
                    reporter TEXT NOT NULL,
                    transcript_snippet TEXT NOT NULL,
                    sensitivity TEXT NOT NULL DEFAULT 'standard',
                    redaction_applied INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            _ensure_column(conn, "facility_tickets", "sensitivity", "TEXT NOT NULL DEFAULT 'standard'")
            _ensure_column(conn, "facility_tickets", "redaction_applied", "INTEGER NOT NULL DEFAULT 0")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facility_audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    ticket_id TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def _validate_create(self, ticket: TicketCreate) -> TicketCreate:
        category = ticket.category.strip().lower()
        urgency = ticket.urgency.strip().lower()
        location = ticket.location.strip()
        summary = ticket.summary.strip()
        reporter = ticket.reporter.strip() or "unknown"
        transcript_snippet = ticket.transcript_snippet.strip()

        if category not in ALLOWED_CATEGORIES:
            raise TicketValidationError(f"category must be one of {', '.join(sorted(ALLOWED_CATEGORIES))}")
        if urgency not in ALLOWED_URGENCIES:
            raise TicketValidationError(f"urgency must be one of {', '.join(sorted(ALLOWED_URGENCIES))}")
        if not location:
            raise TicketValidationError("location is required")
        if not summary:
            raise TicketValidationError("summary is required")

        return TicketCreate(
            category=category,
            location=location,
            summary=summary,
            urgency=urgency,
            reporter=reporter,
            transcript_snippet=transcript_snippet,
        )

    def _validate_update(self, update: TicketUpdate, existing: TicketRecord) -> _NormalizedTicketUpdate:
        status = existing.status if update.status is None else update.status.strip().lower()
        category = existing.category if update.category is None else update.category.strip().lower()
        urgency = existing.urgency if update.urgency is None else update.urgency.strip().lower()
        location = existing.location if update.location is None else update.location.strip()
        summary = existing.summary if update.summary is None else update.summary.strip()
        reporter = existing.reporter if update.reporter is None else update.reporter.strip() or "unknown"
        transcript_snippet = (
            existing.transcript_snippet if update.transcript_snippet is None else update.transcript_snippet.strip()
        )

        if status not in ALLOWED_STATUSES:
            raise TicketValidationError(f"status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
        if category not in ALLOWED_CATEGORIES:
            raise TicketValidationError(f"category must be one of {', '.join(sorted(ALLOWED_CATEGORIES))}")
        if urgency not in ALLOWED_URGENCIES:
            raise TicketValidationError(f"urgency must be one of {', '.join(sorted(ALLOWED_URGENCIES))}")
        if not location:
            raise TicketValidationError("location is required")
        if not summary:
            raise TicketValidationError("summary is required")

        return _NormalizedTicketUpdate(
            status=status,
            category=category,
            location=location,
            summary=summary,
            urgency=urgency,
            reporter=reporter,
            transcript_snippet=transcript_snippet,
        )

    def _redact_ticket(self, ticket: TicketCreate) -> tuple[TicketCreate, bool]:
        if not self.policy.pii_redaction_enabled:
            return ticket, False

        summary, summary_redacted = redact_facility_pii(ticket.summary)
        transcript_snippet, transcript_redacted = redact_facility_pii(ticket.transcript_snippet)
        reporter, reporter_redacted = redact_facility_pii(ticket.reporter)
        return (
            TicketCreate(
                category=ticket.category,
                location=ticket.location,
                summary=summary,
                urgency=ticket.urgency,
                reporter=reporter,
                transcript_snippet=transcript_snippet,
            ),
            summary_redacted or transcript_redacted or reporter_redacted,
        )

    def _insert_audit_event(
        self,
        conn: sqlite3.Connection,
        *,
        event_type: str,
        ticket_id: str,
        actor: str,
        details: dict[str, object],
        created_at: str,
    ) -> None:
        if not self.policy.audit_log_enabled:
            return
        conn.execute(
            """
            INSERT INTO facility_audit_events (
                event_id,
                event_type,
                ticket_id,
                actor,
                details_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                event_type,
                ticket_id,
                actor,
                json.dumps(details, sort_keys=True),
                created_at,
            ),
        )


def _record_from_row(row: sqlite3.Row) -> TicketRecord:
    return TicketRecord(
        ticket_id=row["ticket_id"],
        status=row["status"],
        category=row["category"],
        location=row["location"],
        summary=row["summary"],
        urgency=row["urgency"],
        reporter=row["reporter"],
        transcript_snippet=row["transcript_snippet"],
        sensitivity=row["sensitivity"],
        redaction_applied=bool(row["redaction_applied"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _audit_event_from_row(row: sqlite3.Row) -> AuditEventRecord:
    details = json.loads(row["details_json"])
    return AuditEventRecord(
        event_id=row["event_id"],
        event_type=row["event_type"],
        ticket_id=row["ticket_id"],
        actor=row["actor"],
        details=details if isinstance(details, dict) else {},
        created_at=row["created_at"],
    )


def _changed_fields(
    existing: TicketRecord,
    updated: _NormalizedTicketUpdate,
    sensitivity: str,
    redaction_applied: bool,
) -> list[str]:
    fields: list[str] = []
    for field in ("status", "category", "location", "summary", "urgency", "reporter", "transcript_snippet"):
        if getattr(existing, field) != getattr(updated, field):
            fields.append(field)
    if existing.sensitivity != sensitivity:
        fields.append("sensitivity")
    if existing.redaction_applied != redaction_applied:
        fields.append("redaction_applied")
    return sorted(fields)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing_columns = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing_columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _count(conn: sqlite3.Connection, query: str) -> int:
    return int(conn.execute(query).fetchone()[0])


def _counts_by_value(
    conn: sqlite3.Connection,
    column: str,
    include_values: set[str] | None = None,
) -> dict[str, int]:
    rows = conn.execute(
        f"SELECT {column}, COUNT(*) AS count FROM facility_tickets GROUP BY {column} ORDER BY {column}"
    ).fetchall()
    counts = {row[column]: int(row["count"]) for row in rows}
    if include_values is not None:
        for value in sorted(include_values):
            counts.setdefault(value, 0)
        return {value: counts[value] for value in sorted(counts)}
    return counts


_REDACTION_PATTERNS = (
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[REDACTED_EMAIL]"),
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b[A-Z]\d{7}[A-Z]\b", re.IGNORECASE), "[REDACTED_STUDENT_ID]"),
)


def redact_facility_pii(text: str) -> tuple[str, bool]:
    """Redact common PII patterns from facility ticket text."""
    redacted = text
    for pattern, replacement in _REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted, redacted != text
