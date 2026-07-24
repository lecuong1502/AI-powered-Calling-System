-- Run once when the container is first created.
-- Creates extensions needed by the application.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";   -- for fast LIKE/ILIKE search on phone numbers