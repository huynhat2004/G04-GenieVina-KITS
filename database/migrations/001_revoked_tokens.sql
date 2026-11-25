-- Existing installations only; fresh databases already include this table.
BEGIN;
CREATE TABLE IF NOT EXISTS revoked_tokens (
    token_hash VARCHAR(64) PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS revoked_tokens_expiry_idx ON revoked_tokens(expires_at);
COMMIT;
