CREATE TABLE IF NOT EXISTS files (
    hash TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    size INTEGER NOT NULL,
    ref_count INTEGER NOT NULL DEFAULT 1,
    mime_type TEXT,
    created_at DATETIME NOT NULL
);

ALTER TABLE pastes ADD COLUMN file_hash TEXT;
-- Migrate existing pastes: compute hash? 
-- For simplicity in this migration step, we can't easily migrate old blobs to dedupe without a script.
-- We will leave 'content' in pastes for legacy, but new uploads will use 'file_hash' and 'files' table.
-- Ideally, we would migrate data, but SQL constraints make it hard in one go without external logic.
