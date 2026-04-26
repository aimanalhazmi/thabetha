-- 005 — Tables required by the backend repository that were missing from earlier migrations.
-- Adds: notifications, payment_confirmations, attachments, group_settlements.

-- ── Notifications ──────────────────────────────────────────────
create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  notification_type text not null,
  title text not null,
  body text not null,
  debt_id uuid references public.debts(id) on delete cascade,
  whatsapp_attempted boolean not null default true,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists notifications_user_created_idx
  on public.notifications (user_id, created_at desc);

-- ── Payment confirmations ──────────────────────────────────────
create table if not exists public.payment_confirmations (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null references public.debts(id) on delete cascade,
  debtor_id uuid not null references public.profiles(id) on delete cascade,
  creditor_id uuid not null references public.profiles(id) on delete cascade,
  status text not null,
  note text,
  requested_at timestamptz not null default now(),
  confirmed_at timestamptz
);

create index if not exists payment_confirmations_debt_idx
  on public.payment_confirmations (debt_id);

-- ── Attachments ────────────────────────────────────────────────
create table if not exists public.attachments (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null references public.debts(id) on delete cascade,
  uploader_id uuid not null references public.profiles(id) on delete cascade,
  attachment_type text not null,
  file_name text not null,
  content_type text,
  storage_path text not null,
  public_url text,
  created_at timestamptz not null default now()
);

create index if not exists attachments_debt_idx
  on public.attachments (debt_id);

-- ── Group settlements ──────────────────────────────────────────
create table if not exists public.group_settlements (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.groups(id) on delete cascade,
  payer_id uuid not null references public.profiles(id) on delete cascade,
  debtor_id uuid not null references public.profiles(id) on delete cascade,
  amount numeric(12, 2) not null check (amount > 0),
  currency char(3) not null default 'SAR',
  note text,
  created_at timestamptz not null default now()
);

create index if not exists group_settlements_group_idx
  on public.group_settlements (group_id);

-- ── RLS ────────────────────────────────────────────────────────
alter table public.notifications enable row level security;
alter table public.payment_confirmations enable row level security;
alter table public.attachments enable row level security;
alter table public.group_settlements enable row level security;

drop policy if exists "Users read own notifications" on public.notifications;
create policy "Users read own notifications" on public.notifications
  for select using (auth.uid() = user_id);

drop policy if exists "Users update own notifications" on public.notifications;
create policy "Users update own notifications" on public.notifications
  for update using (auth.uid() = user_id);

drop policy if exists "Parties read payment confirmations" on public.payment_confirmations;
create policy "Parties read payment confirmations" on public.payment_confirmations
  for select using (auth.uid() = debtor_id or auth.uid() = creditor_id);

drop policy if exists "Parties read attachments" on public.attachments;
create policy "Parties read attachments" on public.attachments
  for select using (
    exists (
      select 1 from public.debts d
      where d.id = attachments.debt_id and (auth.uid() = d.creditor_id or auth.uid() = d.debtor_id)
    )
  );

drop policy if exists "Group members read settlements" on public.group_settlements;
create policy "Group members read settlements" on public.group_settlements
  for select using (
    exists (
      select 1 from public.group_members gm
      where gm.group_id = group_settlements.group_id and gm.user_id = auth.uid() and gm.status = 'accepted'
    )
  );
