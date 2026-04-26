-- 003 — Storage RLS for the receipts and voice-notes buckets.
--
-- Policies enforce per-user isolation on Supabase Storage objects so a
-- creditor's receipt cannot be downloaded by anyone outside the debt's
-- creditor/debtor pair. Path convention used by the backend:
--
--   receipts/<debt_id>/<uuid>-<filename>
--   voice-notes/<debt_id>/<uuid>-<filename>
--
-- Authorization is "user is a party to that debt". The first path segment
-- (folder name) is the debt id, which we look up against `public.debts`.

-- Helper: returns true if the calling user is creditor or debtor on a debt.
create or replace function public.user_is_debt_party(_debt_id uuid)
returns boolean
language sql
stable
security definer set search_path = public
as $$
  select exists (
    select 1 from public.debts
    where id = _debt_id
      and (creditor_id = auth.uid() or debtor_id = auth.uid())
  );
$$;

-- Receipts bucket: read + write restricted to debt parties.
drop policy if exists "Receipts: parties can read" on storage.objects;
create policy "Receipts: parties can read" on storage.objects
  for select using (
    bucket_id = 'receipts'
    and public.user_is_debt_party((string_to_array(name, '/'))[1]::uuid)
  );

drop policy if exists "Receipts: parties can write" on storage.objects;
create policy "Receipts: parties can write" on storage.objects
  for insert with check (
    bucket_id = 'receipts'
    and public.user_is_debt_party((string_to_array(name, '/'))[1]::uuid)
  );

-- Voice notes bucket: same model.
drop policy if exists "Voice notes: parties can read" on storage.objects;
create policy "Voice notes: parties can read" on storage.objects
  for select using (
    bucket_id = 'voice-notes'
    and public.user_is_debt_party((string_to_array(name, '/'))[1]::uuid)
  );

drop policy if exists "Voice notes: parties can write" on storage.objects;
create policy "Voice notes: parties can write" on storage.objects
  for insert with check (
    bucket_id = 'voice-notes'
    and public.user_is_debt_party((string_to_array(name, '/'))[1]::uuid)
  );
