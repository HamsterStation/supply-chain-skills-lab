CREATE TABLE oauth_states (id TEXT PRIMARY KEY, verifier TEXT NOT NULL, binding TEXT NOT NULL, app_challenge TEXT NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE handoffs (id TEXT PRIMARY KEY, session_id TEXT NOT NULL, app_challenge TEXT NOT NULL, expires INTEGER NOT NULL);
CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, login TEXT NOT NULL, token_cipher TEXT NOT NULL, expires INTEGER NOT NULL);
CREATE INDEX sessions_expiry ON sessions(expires);
CREATE TABLE accounts (user_id INTEGER PRIMARY KEY, repository TEXT, last_sync_at TEXT);
CREATE TABLE rate_limits (bucket TEXT PRIMARY KEY, count INTEGER NOT NULL, expires INTEGER NOT NULL);
