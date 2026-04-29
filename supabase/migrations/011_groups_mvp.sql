-- ── 011: Groups MVP — surface, lifecycle, audit ────────────────────────────
-- Spec: specs/008-groups-mvp-surface/
--
-- 1. profiles.groups_enabled feature flag (default true).
-- 2. group_member_status enum widened: + 'declined', 'left'.
-- 3. group_members live-row partial-unique index (replaces flat unique).
-- 4. groups.updated_at + maintenance trigger.
-- 5. group_events audit table (FK on delete set null — preserves audit row).
-- 6. notification_type widened: + 'group_invite', 'group_invite_accepted',
--    'group_ownership_transferred'  (only when notification_type is an enum;
--    notifications.type is plain text in this codebase, so this step is a
--    no-op at the DB layer).
-- 7. RLS refresh on groups, group_members, group_events, debts.

-- ── 1. profiles.groups_enabled ───────────────────────────────────────────
alter table public.profiles
  add column if not exists groups_enabled boolean not null default true;

-- New-user trigger reseeded so future inserts pick up the column default
-- explicitly (defensive — Postgres applies the default automatically when
-- a column is omitted, but listing it makes intent clear).
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, name, phone, email, account_type, preferred_language, groups_enabled)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', ''),
    coalesce(new.raw_user_meta_data->>'phone', ''),
    new.email,
    coalesce((new.raw_user_meta_data->>'account_type')::public.account_type, 'debtor'),
    coalesce(new.raw_user_meta_data->>'preferred_language', 'ar'),
    true
  );
  return new;
end;
$$;

-- ── 2. Widen group_member_status enum ────────────────────────────────────
do $$
begin
  if not exists (select 1 from pg_enum
                 where enumtypid = 'public.group_member_status'::regtype
                   and enumlabel = 'declined') then
    alter type public.group_member_status add value 'declined';
  end if;
  if not exists (select 1 from pg_enum
                 where enumtypid = 'public.group_member_status'::regtype
                   and enumlabel = 'left') then
    alter type public.group_member_status add value 'left';
  end if;
end $$;

-- ── 3. Live-row partial-unique index ─────────────────────────────────────
-- Drops the flat (group_id, user_id) unique constraint so a user who
-- declined / left can be re-invited with a fresh pending row alongside
-- their terminal-state audit rows.
alter table public.group_members
  drop constraint if exists group_members_group_id_user_id_key;

create unique index if not exists ux_group_members_live
  on public.group_members (group_id, user_id)
  where status in ('pending', 'accepted');

-- ── 4. groups.updated_at ─────────────────────────────────────────────────
alter table public.groups
  add column if not exists updated_at timestamptz not null default now();

create or replace function public.touch_groups_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists trg_groups_touch on public.groups;
create trigger trg_groups_touch
  before update on public.groups
  for each row execute procedure public.touch_groups_updated_at();

-- ── 5. group_events audit table ──────────────────────────────────────────
-- FK uses on delete set null so the 'deleted' audit row survives group
-- removal — Constitution VIII (audit trail per state transition).
create table if not exists public.group_events (
  id uuid primary key default gen_random_uuid(),
  group_id uuid references public.groups(id) on delete set null,
  actor_id uuid references public.profiles(id) on delete set null,
  event_type text not null check (event_type in (
    'created', 'renamed', 'member_invited', 'member_joined',
    'member_declined', 'member_left', 'invite_revoked',
    'ownership_transferred', 'deleted'
  )),
  message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists ix_group_events_group_created
  on public.group_events (group_id, created_at desc)
  where group_id is not null;

-- ── 6. RLS — groups, group_members, group_events, debts ──────────────────
alter table public.groups enable row level security;
alter table public.group_members enable row level security;
alter table public.group_events enable row level security;

-- groups: select for owner or accepted member; update for owner.
drop policy if exists groups_select on public.groups;
create policy groups_select on public.groups
  for select using (
    auth.uid() = owner_id
    or exists (
      select 1 from public.group_members gm
      where gm.group_id = groups.id
        and gm.user_id = auth.uid()
        and gm.status = 'accepted'
    )
  );

drop policy if exists groups_update on public.groups;
create policy groups_update on public.groups
  for update using (auth.uid() = owner_id) with check (auth.uid() = owner_id);

-- group_members: caller may select their own row, plus rows in any group
-- they are an accepted member of (so members can see each other and the
-- owner can see pending invites for groups they own).
drop policy if exists group_members_select on public.group_members;
create policy group_members_select on public.group_members
  for select using (
    user_id = auth.uid()
    or exists (
      select 1 from public.group_members gm2
      where gm2.group_id = group_members.group_id
        and gm2.user_id = auth.uid()
        and gm2.status = 'accepted'
    )
  );

-- group_events: select for accepted members of the (still-extant) group.
drop policy if exists group_events_select on public.group_events;
create policy group_events_select on public.group_events
  for select using (
    group_id is not null
    and exists (
      select 1 from public.group_members gm
      where gm.group_id = group_events.group_id
        and gm.user_id = auth.uid()
        and gm.status = 'accepted'
    )
  );

-- debts: extend the existing party-only access with a relaxed-privacy
-- predicate for group-tagged debts. Members of the tagged group can read
-- the debt; untagged debts remain strictly party-only (FR-023, FR-025).
-- The historical "Allow debt access" policy granted ALL ops; preserve that
-- shape but include the group-member SELECT branch.
drop policy if exists "Allow debt access" on public.debts;
drop policy if exists debts_select_party_or_group on public.debts;
drop policy if exists debts_write_party on public.debts;

create policy debts_select_party_or_group on public.debts
  for select using (
    auth.uid() = creditor_id
    or auth.uid() = debtor_id
    or (group_id is not null and exists (
      select 1 from public.group_members gm
      where gm.group_id = debts.group_id
        and gm.user_id = auth.uid()
        and gm.status = 'accepted'
    ))
  );

create policy debts_write_party on public.debts
  for all using (auth.uid() = creditor_id or auth.uid() = debtor_id)
  with check (auth.uid() = creditor_id or auth.uid() = debtor_id);
