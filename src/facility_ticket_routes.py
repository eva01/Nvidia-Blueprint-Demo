# SPDX-FileCopyrightText: Copyright (c) 2024-2026, NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: BSD-2-Clause

"""FastAPI routes for school facility ticket storage."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.facility_sovereignty import load_facility_sovereignty_policy
from src.facility_tickets import FacilityTicketStore, TicketCreate, TicketUpdate, TicketValidationError
from src.school_knowledge_base import load_school_knowledge_base

router = APIRouter(prefix="/facility", tags=["facility tickets"])
_store: FacilityTicketStore | None = None


class TicketCreateRequest(BaseModel):
    """API request for creating a facility ticket."""

    category: str
    location: str
    summary: str
    urgency: str = "normal"
    reporter: str = "unknown"
    transcript_snippet: str = ""


class TicketStatusRequest(BaseModel):
    """API request for changing ticket status."""

    status: str


class TicketUpdateRequest(BaseModel):
    """API request for editing a facility ticket."""

    status: str | None = None
    category: str | None = None
    location: str | None = None
    summary: str | None = None
    urgency: str | None = None
    reporter: str | None = None
    transcript_snippet: str | None = None


def get_ticket_store() -> FacilityTicketStore:
    """Return the configured ticket store."""
    global _store
    if _store is None:
        _store = FacilityTicketStore(_ticket_db_path())
    return _store


@router.post("/tickets", status_code=201)
async def create_facility_ticket(payload: TicketCreateRequest) -> dict[str, object]:
    """Create a school facility ticket."""
    try:
        ticket = get_ticket_store().create_ticket(TicketCreate(**_model_dump(payload)))
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ticket.to_dict()


@router.get("/tickets")
async def list_facility_tickets() -> list[dict[str, object]]:
    """List school facility tickets."""
    return [ticket.to_dict() for ticket in get_ticket_store().list_tickets()]


@router.get("/tickets/{ticket_id}")
async def get_facility_ticket(ticket_id: str) -> dict[str, object]:
    """Read a school facility ticket."""
    ticket = get_ticket_store().get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found")
    return ticket.to_dict()


@router.patch("/tickets/{ticket_id}/status")
async def update_facility_ticket_status(ticket_id: str, payload: TicketStatusRequest) -> dict[str, object]:
    """Update school facility ticket status."""
    try:
        ticket = get_ticket_store().update_status(ticket_id, payload.status)
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found") from exc
    return ticket.to_dict()


@router.patch("/tickets/{ticket_id}")
async def update_facility_ticket(ticket_id: str, payload: TicketUpdateRequest) -> dict[str, object]:
    """Update editable school facility ticket fields."""
    try:
        ticket = get_ticket_store().update_ticket(ticket_id, TicketUpdate(**_model_dump(payload)))
    except TicketValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found") from exc
    return ticket.to_dict()


@router.delete("/tickets/{ticket_id}")
async def delete_facility_ticket(ticket_id: str) -> dict[str, object]:
    """Delete a school facility ticket."""
    try:
        deleted = get_ticket_store().delete_ticket(ticket_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_id} not found") from exc
    return {"ticket_id": deleted.ticket_id, "deleted": True}


@router.get("/audit")
async def list_facility_audit_events() -> list[dict[str, object]]:
    """List local facility audit events."""
    return [event.to_dict() for event in get_ticket_store().list_audit_events()]


@router.get("/summary")
async def get_facility_summary() -> dict[str, object]:
    """Return aggregate local facility operations metrics."""
    summary = get_ticket_store().get_summary()
    policy = load_facility_sovereignty_policy()
    summary["sovereignty"] = {
        "mode": policy.mode,
        "data_residency_region": policy.data_residency_region,
        "storage_backend": policy.storage_backend,
        "pii_redaction_enabled": policy.pii_redaction_enabled,
        "audit_log_enabled": policy.audit_log_enabled,
    }
    return summary


@router.get("/knowledge/search")
async def search_school_knowledge(q: str, limit: int = 3) -> list[dict[str, object]]:
    """Search the local school knowledge base."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="q is required")
    kb_path = Path(os.getenv("SCHOOL_KNOWLEDGE_BASE_PATH", "config/school_knowledge_base.yaml"))
    knowledge_base = load_school_knowledge_base(kb_path)
    results = knowledge_base.search(q, limit=max(1, min(limit, 10)), min_score=_env_int("SCHOOL_RAG_MIN_SCORE", 45))
    return [
        {
            "id": result.id,
            "title": result.title,
            "content": result.content,
            "tags": list(result.tags),
            "score": result.score,
        }
        for result in results
    ]


@router.get("/sovereignty")
async def get_facility_sovereignty_status() -> dict[str, object]:
    """Return secret-safe local sovereign AI demo status."""
    policy = load_facility_sovereignty_policy()
    status = policy.to_dict(db_path=_ticket_db_path())
    status["runtime"] = "local"
    status["llm_provider"] = "nvidia_nim"
    status["asr_endpoint_type"] = _endpoint_type(os.getenv("ASR_SERVER_URL", ""))
    status["tts_endpoint_type"] = _endpoint_type(os.getenv("TTS_SERVER_URL", ""))
    status["llm_endpoint_type"] = _endpoint_type(os.getenv("NVIDIA_LLM_URL", ""))
    status["api_key_configured"] = bool(os.getenv("NVIDIA_API_KEY", "").strip())
    return status


def _model_dump(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _ticket_db_path() -> Path:
    return Path(os.getenv("FACILITY_TICKETS_DB_PATH", "data/facility_tickets.db")).expanduser().resolve()


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, "").strip()
    if not raw_value:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


def _endpoint_type(value: str) -> str:
    lowered = value.lower()
    if not lowered:
        return "unset"
    if "nvcf.nvidia.com" in lowered or "integrate.api.nvidia.com" in lowered:
        return "cloud_nim"
    if "localhost" in lowered or "127.0.0.1" in lowered or lowered.startswith("http://nvidia-"):
        return "local"
    return "custom"
