-- ── 016: Group owner debt visibility and creditor-only group creation ─────
-- Groups are owned by a creditor-capable account. Shared group debt visibility
-- is limited to debts attached to the group and owed to that group owner.

drop policy if exists groups_insert_creditors on public.groups;
create policy groups_insert_creditors on public.groups
  for insert with check (
    auth.uid() = owner_id
    and exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and p.account_type in ('creditor', 'both', 'business')
    )
  );

drop policy if exists debts_select_party_or_group on public.debts;
create policy debts_select_party_or_group on public.debts
  for select using (
    auth.uid() = creditor_id
    or auth.uid() = debtor_id
    or (
      group_id is not null
      and exists (
        select 1
        from public.groups g
        join public.group_members viewer_gm
          on viewer_gm.group_id = g.id
         and viewer_gm.user_id = auth.uid()
         and viewer_gm.status = 'accepted'
        join public.group_members debtor_gm
          on debtor_gm.group_id = g.id
         and debtor_gm.user_id = debts.debtor_id
         and debtor_gm.status = 'accepted'
        where g.id = debts.group_id
          and debts.creditor_id = g.owner_id
      )
    )
  );

drop policy if exists debts_write_party on public.debts;
create policy debts_write_party on public.debts
  for all using (auth.uid() = creditor_id or auth.uid() = debtor_id)
  with check (
    auth.uid() = creditor_id
    or auth.uid() = debtor_id
  );
