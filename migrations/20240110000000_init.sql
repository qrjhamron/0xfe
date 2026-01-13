CREATE TABLE IF NOT EXISTS pastes (
    id TEXT PRIMARY KEY,
    content BLOB NOT NULL,
    password_hash TEXT,
    created_at DATETIME NOT NULL,
    expiry DATETIME,
    burn_after_read BOOLEAN NOT NULL DEFAULT 0,
    parent_id TEXT,
    mime_type TEXT,
    filename TEXT
);

CREATE INDEX IF NOT EXISTS idx_expiry ON pastes(expiry);
