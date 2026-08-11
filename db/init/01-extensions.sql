-- Runs once, on an empty data directory only. Migrations own the schema (D4) — this file
-- is for things a migration cannot do because they need database-owner rights.
CREATE EXTENSION IF NOT EXISTS pgcrypto;
