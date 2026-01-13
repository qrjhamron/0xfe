-- Add audit and security metadata columns
ALTER TABLE pastes ADD COLUMN content_hash TEXT;
ALTER TABLE pastes ADD COLUMN client_ip_hash TEXT;
ALTER TABLE pastes ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0;
ALTER TABLE pastes ADD COLUMN last_accessed DATETIME;
ALTER TABLE pastes ADD COLUMN encryption_algo TEXT;
ALTER TABLE pastes ADD COLUMN file_size_bytes INTEGER;
ALTER TABLE pastes ADD COLUMN upload_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP;

-- Create indexes for efficient queries
CREATE INDEX IF NOT EXISTS idx_content_hash ON pastes(content_hash);
CREATE INDEX IF NOT EXISTS idx_created_at ON pastes(created_at);
CREATE INDEX IF NOT EXISTS idx_client_ip_hash ON pastes(client_ip_hash);
CREATE INDEX IF NOT EXISTS idx_expires_at ON pastes(expiry) WHERE expiry IS NOT NULL;

-- Add metadata table for structured storage
CREATE TABLE IF NOT EXISTS paste_metadata (
    paste_id TEXT PRIMARY KEY,
    metadata_json TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (paste_id) REFERENCES pastes(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_metadata_updated ON paste_metadata(updated_at);
