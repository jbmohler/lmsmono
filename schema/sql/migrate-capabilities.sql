-- migrate-capabilities.sql
-- Renames activities/roleactivities to capabilities/rolecapabilities,
-- then seeds the canonical capability set and maps them to roles.
--
-- Safe to run against a database that still has the old names.
-- Run as lms_owner:
--   ./scripts/import-dump.sh scripts/migrate-capabilities.sql
-- Or paste into:
--   ./scripts/psql.sh

BEGIN;

-- -----------------------------------------------------------------------
-- 1. Create or rename tables to reach the canonical schema
-- -----------------------------------------------------------------------

DO $$
BEGIN
  -- Rename old activities table if it exists
  IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'activities') THEN
    ALTER TABLE activities RENAME TO capabilities;
    RAISE NOTICE 'Renamed activities -> capabilities';
  END IF;
  IF EXISTS (SELECT FROM information_schema.columns
             WHERE table_name = 'capabilities' AND column_name = 'act_name') THEN
    ALTER TABLE capabilities RENAME COLUMN act_name TO cap_name;
    RAISE NOTICE 'Renamed act_name -> cap_name';
  END IF;

  -- Create capabilities from scratch if it doesn't exist yet
  IF NOT EXISTS (SELECT FROM pg_tables WHERE tablename = 'capabilities') THEN
    CREATE TABLE capabilities (
      id uuid PRIMARY KEY DEFAULT uuid_generate_v1mc(),
      cap_name character varying(80) UNIQUE,
      description text,
      url character varying(500),
      note text
    );
    RAISE NOTICE 'Created capabilities table';
  END IF;

  -- Rename old roleactivities table if it exists
  IF EXISTS (SELECT FROM pg_tables WHERE tablename = 'roleactivities') THEN
    ALTER TABLE roleactivities RENAME TO rolecapabilities;
    RAISE NOTICE 'Renamed roleactivities -> rolecapabilities';
  END IF;
  IF EXISTS (SELECT FROM information_schema.columns
             WHERE table_name = 'rolecapabilities' AND column_name = 'activityid') THEN
    ALTER TABLE rolecapabilities RENAME COLUMN activityid TO capabilityid;
    RAISE NOTICE 'Renamed activityid -> capabilityid';
  END IF;

  -- Create rolecapabilities from scratch if it doesn't exist yet
  IF NOT EXISTS (SELECT FROM pg_tables WHERE tablename = 'rolecapabilities') THEN
    CREATE TABLE rolecapabilities (
      roleid uuid NOT NULL REFERENCES roles(id),
      capabilityid uuid NOT NULL REFERENCES capabilities(id),
      CONSTRAINT rolecapabilities_pkey PRIMARY KEY (roleid, capabilityid)
    );
    RAISE NOTICE 'Created rolecapabilities table';
  END IF;
END
$$;

-- -----------------------------------------------------------------------
-- 2. Clear old capability/role data and reseed
-- -----------------------------------------------------------------------

TRUNCATE rolecapabilities;
TRUNCATE capabilities CASCADE;

INSERT INTO capabilities (cap_name) VALUES
  ('contacts:read'),
  ('contacts:write'),
  ('contacts:passwords'),
  ('databits:read'),
  ('databits:write'),
  ('accounts:read'),
  ('accounts:write'),
  ('transactions:read'),
  ('transactions:write'),
  ('journals:read'),
  ('journals:write'),
  ('reports:read'),
  ('reports:write'),
  ('admin:roles'),
  ('admin:users');

-- -----------------------------------------------------------------------
-- 3. Map capabilities to roles
-- -----------------------------------------------------------------------

-- Administrator: all capabilities
INSERT INTO rolecapabilities (roleid, capabilityid)
SELECT r.id, c.id
FROM roles r, capabilities c
WHERE r.role_name = 'Administrator';

-- Contacts role
INSERT INTO rolecapabilities (roleid, capabilityid)
SELECT r.id, c.id
FROM roles r, capabilities c
WHERE r.role_name = 'Contacts'
  AND c.cap_name IN ('contacts:read', 'contacts:write', 'contacts:passwords');

-- Accounting role
INSERT INTO rolecapabilities (roleid, capabilityid)
SELECT r.id, c.id
FROM roles r, capabilities c
WHERE r.role_name = 'Accounting'
  AND c.cap_name IN (
    'accounts:read', 'accounts:write',
    'transactions:read', 'transactions:write',
    'journals:read', 'journals:write',
    'reports:read', 'reports:write'
  );

-- Data Bits role
INSERT INTO rolecapabilities (roleid, capabilityid)
SELECT r.id, c.id
FROM roles r, capabilities c
WHERE r.role_name = 'Data Bits'
  AND c.cap_name IN ('databits:read', 'databits:write');

-- Login, User, Roscoe User: no capabilities yet

COMMIT;
