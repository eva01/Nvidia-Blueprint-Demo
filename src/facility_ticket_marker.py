# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""Facility ticket marker parsing and persistence helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.facility_tickets import FacilityTicketStore, TicketCreate, TicketRecord, TicketValidationError

FACILITY_TICKET_MARKER_PREFIX = "FACILITY_TICKET:"
_REQUIRED_FIELDS = {"category", "location", "summary"}


@dataclass(frozen=True)
class FacilityTicketMarkerResult:
    """Result of creating a ticket from a voice-agent marker."""

    ticket: TicketRecord
    speech_text: str


def parse_ticket_marker(text: str) -> TicketCreate | None:
    """Parse a strict facility ticket marker into a ticket payload.

    Normal spoken assistant text returns None. Malformed markers raise
    TicketValidationError so callers can suppress raw marker text from TTS.
    """
    stripped = text.strip()
    if not stripped.startswith(FACILITY_TICKET_MARKER_PREFIX):
        return None

    raw_payload = stripped[len(FACILITY_TICKET_MARKER_PREFIX) :].strip()
    if not raw_payload:
        raise TicketValidationError("facility ticket marker is missing JSON payload")

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise TicketValidationError("facility ticket marker contains invalid JSON") from exc

    if not isinstance(payload, dict):
        raise TicketValidationError("facility ticket marker payload must be an object")

    missing = sorted(field for field in _REQUIRED_FIELDS if not _as_text(payload.get(field)).strip())
    if missing:
        raise TicketValidationError(f"facility ticket marker is missing {', '.join(missing)}")

    return TicketCreate(
        category=_as_text(payload.get("category")),
        location=_as_text(payload.get("location")),
        summary=_as_text(payload.get("summary")),
        urgency=_as_text(payload.get("urgency") or "normal"),
        reporter=_as_text(payload.get("reporter") or "unknown"),
        transcript_snippet=_as_text(payload.get("transcript_snippet") or ""),
    )


def create_ticket_from_marker(
    text: str,
    store: FacilityTicketStore,
) -> FacilityTicketMarkerResult | None:
    """Create a ticket when text is a facility ticket marker."""
    ticket_create = parse_ticket_marker(text)
    if ticket_create is None:
        return None

    ticket = store.create_ticket(ticket_create)
    article = "an" if ticket.urgency == "urgent" else "a"
    speech_text = (
        f"Ticket {ticket.ticket_id} is created for {article} {ticket.urgency} "
        f"{ticket.category} issue in {ticket.location}. "
        "Facilities can review it on the dashboard. Thank you. Goodbye."
    )
    return FacilityTicketMarkerResult(ticket=ticket, speech_text=speech_text)


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)
