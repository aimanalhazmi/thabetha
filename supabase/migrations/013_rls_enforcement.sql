-- 013_rls_enforcement.sql
-- Phase 010 — Backend RLS Enforcement.
-- See specs/010-backend-rls-enforcement/{plan,data-model,quickstart}.md for context.
--
-- This migration introduces three Postgres roles and the policy adjustments
-- required to make RLS the authoritative authorization contract for backend
-- request-scoped queries:
--
--   * authenticator      — login, NOINHERIT, no table privileges; the Postgres
--                          identity used by the request-scoped pool. The
--                          per-request middleware runs `SET LOCAL ROLE
--                          app_authenticated` inside a transaction.
--   * app_authenticated  — NOLOGIN, NOINHERIT, no BYPASSRLS; the role under
--                          which a request actually executes. Row access is
--                          determined by existing policies (which key on
--                          `auth.uid()` / `auth.role()` from the JWT claims).
--   * app_service        — login, NOINHERIT, BYPASSRLS; used only by the
--                          system_pool via repositories/system_tasks.py
--                          (lazy commitment-score sweeper, signup trigger,
--                          future cron-like jobs).
--
-- Policy intent table (applies once enforcement is enabled):
--
--   table                              | SELECT                              | INSERT       | UPDATE       | DELETE
--   -----------------------------------+-------------------------------------+--------------+--------------+-------
--   profiles                           | own row OR any authenticated caller | own row only | own row only | denied
--                                      | (preview — endpoint projects fields)|              |              |
--   business_profiles                  | owner only                          | owner only   | owner only   | owner only
--   debts                              | creditor / debtor / accepted member | creditor    | creditor / debtor (per existing) | denied at row layer
--   debt_events                        | creditor / debtor of debt           | app_service | denied       | denied
--   commitment_score_events            | own row                             | app_service | denied       | denied
--   notifications                      | recipient                           | app_service | recipient    | denied
--   attachments                        | parties of the parent debt          | parties     | denied       | creditor of debt
--   groups, group_members, settlements | accepted member of the group        | per existing 011/012 policies                |
--
-- Stale-claim / deleted-user behavior (T013a, spec edge case): policies that
-- key on `auth.uid()` continue to evaluate against the JWT `sub` claim even if
-- the corresponding `auth.users` row has been deleted. We rely on token expiry
-- (default Supabase session = 1 hour) plus token-revocation on user delete.
-- A stricter `EXISTS (SELECT 1 FROM auth.users WHERE id = auth.uid())` predicate
-- can be added in a follow-up if observed token-replay-after-delete becomes
-- a real concern. Documented here so the test in
-- backend/tests/rls/test_isolation_negative.py::test_deleted_user_denied_under_stale_token
-- can encode the chosen policy.
--
-- Operator playbook for flipping RLS_MODE: specs/010-backend-rls-enforcement/quickstart.md §1.

-- ── Roles ──────────────────────────────────────────────────────
-- Idempotent role creation. Passwords are NULL here; they MUST be set out-of-band
-- (e.g., by the deployment configuration) and then surfaced via APP_DATABASE_URL
-- and SYSTEM_DATABASE_URL. Using NULL here keeps the migration safe to run in
-- environments that already have these roles configured.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'app_authenticated') then
    create role app_authenticated nologin noinherit;
  end if;

  if not exists (select 1 from pg_roles where rolname = 'authenticator') then
    create role authenticator login noinherit;
  end if;

  if not exists (select 1 from pg_roles where rolname = 'app_service') then
    create role app_service login noinherit bypassrls;
  end if;
end
$$;

-- authenticator must be allowed to SET ROLE app_authenticated (and only that).
grant app_authenticated to authenticator;

-- ── Schema usage ────────────────────────────────────────────────
grant usage on schema public to app_authenticated, app_service;
grant usage on schema auth   to app_authenticated, app_service;

-- ── Table-level DML grants ──────────────────────────────────────
-- app_authenticated: row access is policy-driven; we grant the verbs at table
-- level here. Field-level restrictions on profiles are enforced at the API
-- handler layer (see FR-014 + quickstart.md §2.3); column-level GRANTs are a
-- follow-up that does not block this phase.

grant select, insert, update, delete on
  public.profiles,
  public.business_profiles,
  public.merchant_notification_preferences,
  public.debts,
  public.debt_events,
  public.commitment_score_events,
  public.notifications,
  public.payment_confirmations,
  public.payment_intents,
  public.attachments,
  public.qr_tokens,
  public.groups,
  public.group_members,
  public.group_events,
  public.group_settlements,
  public.group_settlement_proposals,
  public.group_settlement_confirmations
to app_authenticated;

grant usage, select on all sequences in schema public to app_authenticated;
alter default privileges in schema public
  grant usage, select on sequences to app_authenticated;

-- app_service bypasses RLS entirely; broad DML for sweeper/trigger paths.
grant select, insert, update, delete on all tables in schema public to app_service;
grant usage, select on all sequences in schema public to app_service;
alter default privileges in schema public
  grant select, insert, update, delete on tables to app_service;
alter default privileges in schema public
  grant usage, select on sequences to app_service;

-- ── Profiles: public-preview policy (FR-014 / QR-resolve) ──────
-- Existing policy "Allow profile access" is ALL with auth.uid() = id (own-row).
-- Add a SELECT-only policy that lets any authenticated caller read other rows
-- for QR-preview. Field-level exposure is bounded by the API endpoint, which
-- already projects only the public-preview field set; the policy intentionally
-- does not duplicate that field-set restriction in SQL — see FR-014 rationale.

drop policy if exists "Profiles preview for authenticated" on public.profiles;
create policy "Profiles preview for authenticated"
  on public.profiles
  for select
  using (auth.role() = 'authenticated');

-- ── New-table baseline convention (FR-012 / SC-007) ────────────
-- Future migrations that add user-data tables MUST:
--   1. alter table <t> enable row level security;
--   2. create at least one policy (or an explicit deny-all baseline);
--   3. grant the appropriate verbs to app_authenticated (table or column level);
--   4. document the access shape in the migration header.
-- A migration-lint test (T034a, backend/tests/rls/test_migration_lint.py) will
-- enforce items 1 & 2 once it lands. Items 3 & 4 are review-time concerns.

-- ── Sanity check (informational) ───────────────────────────────
-- The following query, run by an operator post-migration, should list all
-- public-schema tables that have RLS disabled (expect zero results except
-- for known-public utility tables):
--
--   select n.nspname, c.relname
--     from pg_class c join pg_namespace n on c.relnamespace = n.oid
--    where n.nspname = 'public'
--      and c.relkind = 'r'
--      and not c.relrowsecurity;
