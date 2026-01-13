CREATE TABLE pastes_new (
    id TEXT PRIMARY KEY,
    content BLOB, -- Now nullable
    password_hash TEXT,
    created_at DATETIME NOT NULL,
    expiry DATETIME,
    burn_after_read BOOLEAN NOT NULL DEFAULT 0,
    parent_id TEXT,
    mime_type TEXT,
    filename TEXT,
    file_hash TEXT
);

INSERT INTO pastes_new (id, content, password_hash, created_at, expiry, burn_after_read, parent_id, mime_type, filename, file_hash)
SELECT id, content, password_hash, created_at, expiry, burn_after_read, parent_id, mime_type, filename, file_hash FROM pastes;

DROP TABLE pastes;
ALTER TABLE pastes_new RENAME TO pastes;
CREATE INDEX idx_expiry ON pastes(expiry);
