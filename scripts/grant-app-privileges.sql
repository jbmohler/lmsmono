-- grant-app-privileges.sql
-- Grants the app user (lms) access to all non-public schemas.
-- Run this after importing a dump or whenever new schemas are added.
--
-- Run as lms_owner:
--   ./scripts/import-dump.sh scripts/grant-app-privileges.sql
-- Or as the admin user via psql.sh if lms_owner doesn't own the objects.

DO $$
DECLARE
  schemas TEXT[] := ARRAY['public', 'contacts', 'hacc', 'yenotsys'];
  s TEXT;
BEGIN
  FOREACH s IN ARRAY schemas LOOP
    IF EXISTS (SELECT FROM information_schema.schemata WHERE schema_name = s) THEN
      EXECUTE format('GRANT USAGE ON SCHEMA %I TO lms_server', s);
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA %I TO lms_server', s);
      EXECUTE format('GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA %I TO lms_server', s);
      RAISE NOTICE 'Granted privileges on schema: %', s;
    ELSE
      RAISE NOTICE 'Schema % does not exist, skipping', s;
    END IF;
  END LOOP;
END
$$;

-- Set default privileges so future objects are also covered
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lms_server;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA public
  GRANT USAGE, SELECT ON SEQUENCES TO lms_server;

ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA contacts
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lms_server;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA contacts
  GRANT USAGE, SELECT ON SEQUENCES TO lms_server;

ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA hacc
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lms_server;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA hacc
  GRANT USAGE, SELECT ON SEQUENCES TO lms_server;

ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA yenotsys
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO lms_server;
ALTER DEFAULT PRIVILEGES FOR ROLE lms_owner IN SCHEMA yenotsys
  GRANT USAGE, SELECT ON SEQUENCES TO lms_server;
