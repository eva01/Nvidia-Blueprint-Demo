import assert from "node:assert/strict";
import { test } from "node:test";

import {
  FACILITY_TICKET_CREATED_FALLBACK_STOP_DELAY_MS,
  FACILITY_TICKET_CREATED_STOP_DELAY_MS,
  isFacilityTicketClosingTranscript,
  shouldReturnToDashboardAfterTicketCreated,
} from "./voiceSession.ts";

test("facility ticket created stop delay gives TTS time to speak the closing", () => {
  assert.ok(FACILITY_TICKET_CREATED_STOP_DELAY_MS >= 11000);
  assert.ok(FACILITY_TICKET_CREATED_FALLBACK_STOP_DELAY_MS > FACILITY_TICKET_CREATED_STOP_DELAY_MS);
});

test("ticket created flow waits before returning to dashboard", () => {
  assert.equal(shouldReturnToDashboardAfterTicketCreated(0), false);
  assert.equal(shouldReturnToDashboardAfterTicketCreated(FACILITY_TICKET_CREATED_STOP_DELAY_MS - 1), false);
  assert.equal(shouldReturnToDashboardAfterTicketCreated(FACILITY_TICKET_CREATED_STOP_DELAY_MS), true);
});

test("ticket created flow waits for the closing bot transcript before normal return", () => {
  assert.equal(
    isFacilityTicketClosingTranscript(
      "Ticket FAC-000123 is created for an urgent safety issue in Science lab 2. Facilities can review it on the dashboard. Thank you. Goodbye.",
      "FAC-000123"
    ),
    true
  );
  assert.equal(isFacilityTicketClosingTranscript("What location should I use?", "FAC-000123"), false);
  assert.equal(isFacilityTicketClosingTranscript("Ticket FAC-000999 is created. Thank you.", "FAC-000123"), false);
});
