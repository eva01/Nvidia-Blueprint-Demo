import assert from "node:assert/strict";
import { test } from "node:test";

import {
  deleteFacilityTicket,
  formatTicketStatus,
  updateFacilityTicket,
  updateFacilityTicketStatus,
  type FacilityTicket,
} from "./facilityTickets.ts";

test("formatTicketStatus presents backend statuses for operators", () => {
  assert.equal(formatTicketStatus("open"), "Open");
  assert.equal(formatTicketStatus("in_progress"), "In progress");
  assert.equal(formatTicketStatus("resolved"), "Closed");
});

test("updateFacilityTicketStatus patches resolved status for close action", async () => {
  const calls: Array<[string, RequestInit | undefined]> = [];
  const updatedTicket: FacilityTicket = {
    ticket_id: "FAC-000001",
    status: "resolved",
    category: "hvac",
    location: "Block A",
    summary: "Air conditioner is leaking.",
    urgency: "urgent",
    reporter: "unknown",
    transcript_snippet: "",
    sensitivity: "standard",
    redaction_applied: false,
    created_at: "2026-06-21T20:00:00Z",
    updated_at: "2026-06-21T20:01:00Z",
  };
  const fetchImpl = async (url: string, init?: RequestInit) => {
    calls.push([url, init]);
    return {
      ok: true,
      json: async () => updatedTicket,
    } as Response;
  };

  const result = await updateFacilityTicketStatus(
    "FAC-000001",
    "resolved",
    "http://127.0.0.1:7860",
    fetchImpl
  );

  assert.equal(result.status, "resolved");
  assert.equal(calls[0][0], "http://127.0.0.1:7860/facility/tickets/FAC-000001/status");
  assert.equal(calls[0][1]?.method, "PATCH");
  assert.equal(calls[0][1]?.body, JSON.stringify({ status: "resolved" }));
});

test("updateFacilityTicket patches editable ticket fields", async () => {
  const calls: Array<[string, RequestInit | undefined]> = [];
  const updatedTicket: FacilityTicket = {
    ticket_id: "FAC-000001",
    status: "in_progress",
    category: "safety",
    location: "Science lab 2",
    summary: "Water near an outlet.",
    urgency: "urgent",
    reporter: "Jin",
    transcript_snippet: "Reporter said water is near the outlet.",
    sensitivity: "standard",
    redaction_applied: false,
    created_at: "2026-06-21T20:00:00Z",
    updated_at: "2026-06-21T20:01:00Z",
  };
  const fetchImpl = async (url: string, init?: RequestInit) => {
    calls.push([url, init]);
    return {
      ok: true,
      json: async () => updatedTicket,
    } as Response;
  };

  const result = await updateFacilityTicket(
    "FAC-000001",
    { status: "in_progress", category: "safety", location: "Science lab 2", summary: "Water near an outlet.", urgency: "urgent", reporter: "Jin", transcript_snippet: "Reporter said water is near the outlet." },
    "http://127.0.0.1:7860",
    fetchImpl
  );

  assert.equal(result.location, "Science lab 2");
  assert.equal(calls[0][0], "http://127.0.0.1:7860/facility/tickets/FAC-000001");
  assert.equal(calls[0][1]?.method, "PATCH");
});

test("deleteFacilityTicket deletes by ticket id", async () => {
  const calls: Array<[string, RequestInit | undefined]> = [];
  const fetchImpl = async (url: string, init?: RequestInit) => {
    calls.push([url, init]);
    return {
      ok: true,
      json: async () => ({ ticket_id: "FAC-000001", deleted: true }),
    } as Response;
  };

  const result = await deleteFacilityTicket("FAC-000001", "http://127.0.0.1:7860", fetchImpl);

  assert.deepEqual(result, { ticket_id: "FAC-000001", deleted: true });
  assert.equal(calls[0][0], "http://127.0.0.1:7860/facility/tickets/FAC-000001");
  assert.equal(calls[0][1]?.method, "DELETE");
});
