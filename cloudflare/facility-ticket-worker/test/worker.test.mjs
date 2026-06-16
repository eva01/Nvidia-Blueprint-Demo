import assert from "node:assert/strict";
import test from "node:test";

import worker from "../src/index.mjs";

class FakeD1 {
  constructor() {
    this.rows = [];
  }

  prepare(sql) {
    return new FakeStatement(this, sql);
  }
}

class FakeStatement {
  constructor(db, sql) {
    this.db = db;
    this.sql = sql;
    this.values = [];
  }

  bind(...values) {
    this.values = values;
    return this;
  }

  async run() {
    if (this.sql.startsWith("CREATE TABLE")) {
      return { success: true };
    }

    if (this.sql.startsWith("INSERT INTO facility_tickets")) {
      const id = this.db.rows.length + 1;
      const ticketId = `FAC-${String(id).padStart(6, "0")}`;
      const now = "2026-06-21T00:00:00Z";
      const [status, category, location, summary, urgency, reporter, transcriptSnippet] = this.values;
      this.db.rows.push({
        id,
        ticket_id: ticketId,
        status,
        category,
        location,
        summary,
        urgency,
        reporter,
        transcript_snippet: transcriptSnippet,
        created_at: now,
        updated_at: now,
      });
      return { success: true };
    }

    if (this.sql.startsWith("UPDATE facility_tickets SET status")) {
      const [status, updatedAt, ticketId] = this.values;
      const row = this.db.rows.find((candidate) => candidate.ticket_id === ticketId);
      if (row) {
        row.status = status;
        row.updated_at = updatedAt;
        return { success: true, meta: { changes: 1 } };
      }
      return { success: true, meta: { changes: 0 } };
    }

    throw new Error(`Unexpected run SQL: ${this.sql}`);
  }

  async all() {
    if (this.sql.includes("FROM facility_tickets") && this.sql.includes("ORDER BY id ASC")) {
      return { results: this.db.rows.map(rowToApi) };
    }
    throw new Error(`Unexpected all SQL: ${this.sql}`);
  }

  async first() {
    if (/ORDER BY id DESC\s+LIMIT 1/.test(this.sql)) {
      const row = this.db.rows.at(-1);
      return row ? rowToApi(row) : null;
    }

    if (this.sql.includes("FROM facility_tickets") && this.sql.includes("WHERE ticket_id = ?")) {
      const [ticketId] = this.values;
      const row = this.db.rows.find((candidate) => candidate.ticket_id === ticketId);
      return row ? rowToApi(row) : null;
    }

    throw new Error(`Unexpected first SQL: ${this.sql}`);
  }
}

function rowToApi(row) {
  return {
    ticket_id: row.ticket_id,
    status: row.status,
    category: row.category,
    location: row.location,
    summary: row.summary,
    urgency: row.urgency,
    reporter: row.reporter,
    transcript_snippet: row.transcript_snippet,
    created_at: row.created_at,
    updated_at: row.updated_at,
  };
}

function makeEnv() {
  return {
    DB: new FakeD1(),
    OPERATOR_API_TOKEN: "test-operator-token",
    ALLOWED_ORIGIN: "https://operator.example",
  };
}

async function request(env, path, init = {}) {
  const headers = new Headers(init.headers);
  if (path.startsWith("/facility/tickets") && !headers.has("authorization")) {
    headers.set("authorization", `Bearer ${env.OPERATOR_API_TOKEN}`);
  }
  return worker.fetch(new Request(`https://facility.example${path}`, { ...init, headers }), env, {
    waitUntil() {},
    passThroughOnException() {},
  });
}

test("creates, lists, reads, and updates facility tickets", async () => {
  const env = makeEnv();

  const createResponse = await request(env, "/facility/tickets", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      category: "hvac",
      location: "Classroom 3A",
      summary: "Air conditioner leaking near an electrical plug.",
      urgency: "urgent",
      reporter: "Ms Tan",
      transcript_snippet: "The air conditioner in classroom 3A is leaking near a plug.",
    }),
  });

  assert.equal(createResponse.status, 201);
  assert.equal((await createResponse.json()).ticket_id, "FAC-000001");

  const listResponse = await request(env, "/facility/tickets");
  assert.equal(listResponse.status, 200);
  assert.equal((await listResponse.json()).length, 1);

  const updateResponse = await request(env, "/facility/tickets/FAC-000001/status", {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ status: "in_progress" }),
  });
  assert.equal(updateResponse.status, 200);
  assert.equal((await updateResponse.json()).status, "in_progress");

  const readResponse = await request(env, "/facility/tickets/FAC-000001");
  assert.equal(readResponse.status, 200);
  assert.equal((await readResponse.json()).reporter, "Ms Tan");
});

test("rejects invalid ticket payloads", async () => {
  const env = makeEnv();

  const response = await request(env, "/facility/tickets", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      category: "gardening",
      location: "",
      summary: "",
      urgency: "critical",
    }),
  });

  assert.equal(response.status, 400);
  assert.match(await response.text(), /category/);
});

test("requires operator auth for ticket endpoints", async () => {
  const env = makeEnv();

  const missingTokenResponse = await worker.fetch(new Request("https://facility.example/facility/tickets"), env, {
    waitUntil() {},
    passThroughOnException() {},
  });
  assert.equal(missingTokenResponse.status, 401);

  const unconfiguredEnv = { DB: new FakeD1() };
  const unconfiguredResponse = await worker.fetch(
    new Request("https://facility.example/facility/tickets", {
      headers: { authorization: "Bearer test-operator-token" },
    }),
    unconfiguredEnv,
    {
      waitUntil() {},
      passThroughOnException() {},
    }
  );
  assert.equal(unconfiguredResponse.status, 503);
});

test("uses a configured CORS origin", async () => {
  const env = makeEnv();

  const response = await request(env, "/facility/tickets", {
    headers: { origin: "https://operator.example" },
  });

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("access-control-allow-origin"), "https://operator.example");
});

test("serves a small operator landing page", async () => {
  const response = await request(makeEnv(), "/");

  assert.equal(response.status, 200);
  assert.equal(response.headers.get("content-type"), "text/html; charset=utf-8");
  assert.match(await response.text(), /School Facility Tickets/);
});
