CREATE TABLE IF NOT EXISTS tickets (
 id INTEGER PRIMARY KEY,
 title TEXT NOT NULL, description TEXT NOT NULL,
 category TEXT NOT NULL CHECK(category IN ('Network','Access','Hardware','Software')),
 priority TEXT NOT NULL CHECK(priority IN ('Low','Normal','High')),
 status TEXT NOT NULL DEFAULT 'Open' CHECK(status IN ('Open','In progress','Resolved')),
 version INTEGER NOT NULL DEFAULT 1,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS activity (
 id INTEGER PRIMARY KEY,
 ticket_id INTEGER NOT NULL REFERENCES tickets(id),
 body TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS activity_ticket ON activity(ticket_id,id);
