-- Migration 006: Clerk authentication mapping (FN8-689)
-- Adds the identity columns required by clerk_auth.get_current_user:
--   users.clerk_user_id  — links a Clerk user (JWT `sub`) to a Remixa row
--   users.role           — RBAC role read by rbac.require_role
-- Apply AFTER 005_advanced_features.sql. Idempotent (safe to re-run).
--
-- ⚠️ This is a Type-1 schema change on a money-system DB — apply manually with Stefan's
--    ratification (no auto-apply path exists; see FN8-701). Deploy clerk_auth.py only AFTER this.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS clerk_user_id VARCHAR(255);

ALTER TABLE users
ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'user'
    CHECK (role IN ('user', 'creator', 'moderator', 'admin'));

-- One Clerk identity per user; partial unique index ignores legacy NULL rows.
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_clerk_user_id
    ON users(clerk_user_id) WHERE clerk_user_id IS NOT NULL;

-- Index only the non-default roles (the rows RBAC actually privileges).
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role) WHERE role <> 'user';

-- No role is granted by default. Promote admins explicitly, e.g.:
--   UPDATE users SET role = 'admin' WHERE email = 'stefan@floorno8.com';

-- ============================================================================
-- ROLLBACK
-- ============================================================================
-- DROP INDEX IF EXISTS idx_users_role;
-- DROP INDEX IF EXISTS idx_users_clerk_user_id;
-- ALTER TABLE users DROP COLUMN IF EXISTS role;
-- ALTER TABLE users DROP COLUMN IF EXISTS clerk_user_id;
