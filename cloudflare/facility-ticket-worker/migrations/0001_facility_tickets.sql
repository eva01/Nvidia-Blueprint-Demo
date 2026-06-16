CREATE TABLE IF NOT EXISTS facility_tickets (
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
);
