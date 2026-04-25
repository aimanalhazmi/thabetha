-- Bootstrap script for GoTrue (Supabase Auth).
-- Runs at Postgres init time, before GoTrue starts.

-- Role that GoTrue uses to manage auth tables
CREATE ROLE supabase_auth_admin LOGIN PASSWORD 'thabetha_local';

-- Auth schema where GoTrue stores users, sessions, etc.
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION supabase_auth_admin;

-- GoTrue needs full control of its schema
GRANT ALL ON SCHEMA auth TO supabase_auth_admin;
GRANT ALL ON SCHEMA public TO supabase_auth_admin;

-- Allow the app user to read auth.users (for FK references from profiles)
GRANT USAGE ON SCHEMA auth TO thabetha;
GRANT SELECT ON ALL TABLES IN SCHEMA auth TO thabetha;

-- Ensure future tables created by GoTrue are also readable
ALTER DEFAULT PRIVILEGES FOR ROLE supabase_auth_admin IN SCHEMA auth
    GRANT SELECT ON TABLES TO thabetha;
