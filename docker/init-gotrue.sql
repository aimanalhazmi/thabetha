-- DB bootstrap script. Runs once on first Postgres init.
-- POSTGRES_USER is "postgres" (superuser). We create the app role here.

CREATE ROLE thabetha LOGIN PASSWORD 'thabetha_local';
GRANT ALL ON DATABASE thabetha TO thabetha;
GRANT ALL ON SCHEMA public TO thabetha;
