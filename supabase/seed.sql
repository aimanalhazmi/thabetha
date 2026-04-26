-- Local seed data — applied automatically by `supabase db reset`.
-- Creates two demo profiles so the local stack is usable without manual signup.
-- These IDs intentionally do NOT exist in auth.users; clear them and sign up
-- for real accounts before testing the full Supabase Auth round-trip.

-- A single demo creditor/debtor pair is enough to exercise the bilateral flow.
-- Comment-out for an empty database.

-- insert into public.profiles (id, name, phone, email, account_type, commitment_score)
-- values
--   ('00000000-0000-0000-0000-000000000001', 'Baqala Al Noor', '+966500000001',
--    'merchant@example.test', 'creditor', 50),
--   ('00000000-0000-0000-0000-000000000002', 'Ahmed', '+966500000002',
--    'customer@example.test', 'debtor', 60)
-- on conflict (id) do nothing;
