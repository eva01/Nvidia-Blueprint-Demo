const ALLOWED_CATEGORIES = new Set(["hvac", "electrical", "plumbing", "it", "furniture", "safety", "cleaning", "other"]);
const ALLOWED_STATUSES = new Set(["open", "in_progress", "resolved"]);
const ALLOWED_URGENCIES = new Set(["low", "normal", "urgent"]);

export default {
  async fetch(request, env) {
    await ensureSchema(env.DB);

    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(request, env) });
    }

    if (request.method === "GET" && path === "/") {
      return htmlResponse(landingPage(), request, env);
    }

    if (request.method === "GET" && path === "/health") {
      return jsonResponse({ ok: true, service: "facility-ticket-worker" }, { request, env });
    }

    if (path.startsWith("/facility/tickets")) {
      const authResponse = requireOperatorAuth(request, env);
      if (authResponse) return authResponse;
    }

    if (path === "/facility/tickets" && request.method === "GET") {
      const { results } = await env.DB.prepare(
        `SELECT ticket_id, status, category, location, summary, urgency,
                reporter, transcript_snippet, created_at, updated_at
           FROM facility_tickets
          ORDER BY id ASC`
      ).all();
      return jsonResponse(results ?? [], { request, env });
    }

    if (path === "/facility/tickets" && request.method === "POST") {
      const payload = await readJson(request);
      const validation = validateCreate(payload);
      if (!validation.ok) {
        return jsonResponse({ error: validation.message }, { status: 400, request, env });
      }

      const now = utcNow();
      await env.DB.prepare(
        `INSERT INTO facility_tickets (
           status, category, location, summary, urgency, reporter,
           transcript_snippet, created_at, updated_at
         )
         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`
      )
        .bind(
          "open",
          validation.ticket.category,
          validation.ticket.location,
          validation.ticket.summary,
          validation.ticket.urgency,
          validation.ticket.reporter,
          validation.ticket.transcript_snippet,
          now,
          now
        )
        .run();

      const created = await env.DB.prepare(
        `SELECT ticket_id, status, category, location, summary, urgency,
                reporter, transcript_snippet, created_at, updated_at
           FROM facility_tickets
          ORDER BY id DESC
          LIMIT 1`
      ).first();
      return jsonResponse(created, { status: 201, request, env });
    }

    const ticketMatch = path.match(/^\/facility\/tickets\/(FAC-\d{6})$/);
    if (ticketMatch && request.method === "GET") {
      const ticket = await readTicket(env.DB, ticketMatch[1]);
      return ticket ? jsonResponse(ticket, { request, env }) : jsonResponse({ error: "ticket not found" }, { status: 404, request, env });
    }

    const statusMatch = path.match(/^\/facility\/tickets\/(FAC-\d{6})\/status$/);
    if (statusMatch && request.method === "PATCH") {
      const payload = await readJson(request);
      const status = String(payload.status ?? "").trim().toLowerCase();
      if (!ALLOWED_STATUSES.has(status)) {
        return jsonResponse({ error: `status must be one of ${[...ALLOWED_STATUSES].sort().join(", ")}` }, { status: 400, request, env });
      }

      const result = await env.DB.prepare("UPDATE facility_tickets SET status = ?, updated_at = ? WHERE ticket_id = ?")
        .bind(status, utcNow(), statusMatch[1])
        .run();

      if ((result.meta?.changes ?? 0) === 0) {
        return jsonResponse({ error: "ticket not found" }, { status: 404, request, env });
      }

      return jsonResponse(await readTicket(env.DB, statusMatch[1]), { request, env });
    }

    return jsonResponse({ error: "not found" }, { status: 404, request, env });
  },
};

async function ensureSchema(db) {
  await db.prepare(
    `CREATE TABLE IF NOT EXISTS facility_tickets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      ticket_id TEXT GENERATED ALWAYS AS ('FAC-' || printf('%06d', id)) STORED UNIQUE,
      status TEXT NOT NULL,
      category TEXT NOT NULL,
      location TEXT NOT NULL,
      summary TEXT NOT NULL,
      urgency TEXT NOT NULL,
      reporter TEXT NOT NULL,
      transcript_snippet TEXT NOT NULL,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    )`
  ).run();
}

async function readTicket(db, ticketId) {
  return db.prepare(
    `SELECT ticket_id, status, category, location, summary, urgency,
            reporter, transcript_snippet, created_at, updated_at
       FROM facility_tickets
      WHERE ticket_id = ?`
  )
    .bind(ticketId)
    .first();
}

function validateCreate(payload) {
  const category = String(payload.category ?? "").trim().toLowerCase();
  const urgency = String(payload.urgency ?? "normal").trim().toLowerCase();
  const location = String(payload.location ?? "").trim();
  const summary = String(payload.summary ?? "").trim();
  const reporter = String(payload.reporter ?? "unknown").trim() || "unknown";
  const transcriptSnippet = String(payload.transcript_snippet ?? "").trim();

  if (!ALLOWED_CATEGORIES.has(category)) {
    return { ok: false, message: `category must be one of ${[...ALLOWED_CATEGORIES].sort().join(", ")}` };
  }
  if (!ALLOWED_URGENCIES.has(urgency)) {
    return { ok: false, message: `urgency must be one of ${[...ALLOWED_URGENCIES].sort().join(", ")}` };
  }
  if (!location) {
    return { ok: false, message: "location is required" };
  }
  if (!summary) {
    return { ok: false, message: "summary is required" };
  }

  return {
    ok: true,
    ticket: {
      category,
      location,
      summary,
      urgency,
      reporter,
      transcript_snippet: transcriptSnippet,
    },
  };
}

async function readJson(request) {
  try {
    return await request.json();
  } catch {
    return {};
  }
}

function requireOperatorAuth(request, env) {
  const token = String(env.OPERATOR_API_TOKEN ?? "").trim();
  if (!token) {
    return jsonResponse({ error: "operator API token is not configured" }, { status: 503, request, env });
  }

  const authorization = request.headers.get("authorization") ?? "";
  if (authorization !== `Bearer ${token}`) {
    return jsonResponse({ error: "unauthorized" }, { status: 401, request, env });
  }

  return null;
}

function jsonResponse(data, init = {}) {
  const { request, env, headers, ...responseInit } = init;
  return new Response(JSON.stringify(data), {
    ...responseInit,
    headers: {
      "content-type": "application/json; charset=utf-8",
      ...corsHeaders(request, env),
      ...(headers ?? {}),
    },
  });
}

function htmlResponse(body, request, env) {
  return new Response(body, {
    headers: {
      "content-type": "text/html; charset=utf-8",
      ...corsHeaders(request, env),
    },
  });
}

function corsHeaders(request, env) {
  const allowedOrigin = String(env?.ALLOWED_ORIGIN ?? "http://127.0.0.1:9000").trim();
  const requestOrigin = request?.headers.get("origin") ?? "";
  const origin = requestOrigin === allowedOrigin ? requestOrigin : allowedOrigin;
  return {
    "access-control-allow-origin": origin,
    "access-control-allow-methods": "GET, POST, PATCH, OPTIONS",
    "access-control-allow-headers": "content-type, authorization",
    "vary": "Origin",
  };
}

function utcNow() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

function landingPage() {
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <title>School Facility Tickets</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 2rem; line-height: 1.5; color: #111827; }
      code { background: #f3f4f6; padding: 0.15rem 0.3rem; border-radius: 0.25rem; }
      main { max-width: 760px; }
    </style>
  </head>
  <body>
    <main>
      <h1>School Facility Tickets</h1>
      <p>Cloudflare-hosted operator API for the Nemotron voice facility-support demo.</p>
      <p>Use <code>GET /facility/tickets</code>, <code>POST /facility/tickets</code>, and
      <code>PATCH /facility/tickets/FAC-000001/status</code>.</p>
    </main>
  </body>
</html>`;
}
