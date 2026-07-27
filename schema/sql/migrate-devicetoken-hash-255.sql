-- migrate-devicetoken-hash-255.sql
-- Widens the device-token / session refresh hash columns from varchar(60)
-- to varchar(255) so they can hold an Argon2 hash (~97 chars), matching how
-- users.pwhash already stores password hashes.
--
-- The 60-char width predated the decision to hash remember-me tokens with
-- Argon2; an Argon2id encoding does not fit in 60 characters and would be
-- silently truncated, breaking verification.
--
-- Safe to run repeatedly: widening a varchar length is idempotent and
-- preserves existing values (all columns are unused today).
--
-- Run as lms_owner:
--   ./scripts/import-dump.sh scripts/migrate-devicetoken-hash-255.sql
-- Or paste into:
--   ./scripts/psql.sh

BEGIN;

ALTER TABLE devicetokens ALTER COLUMN tokenhash    TYPE varchar(255);
ALTER TABLE sessions     ALTER COLUMN refresh_hash TYPE varchar(255);

COMMIT;
