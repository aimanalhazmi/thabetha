-- Thabetha Schema — uses Supabase auth.users for authentication
create extension if not exists pgcrypto;

-- ── Enums ──────────────────────────────────────────────────────
create type account_type as enum ('creditor', 'debtor', 'both');
create type debt_status as enum ('waiting_for_confirmation', 'active', 'paid', 'delay');
create type attachment_type as enum ('invoice', 'voice_note', 'other');
create type group_member_status as enum ('pending', 'accepted');

-- ── Profiles ───────────────────────────────────────────────────
-- References auth.users managed by Supabase GoTrue
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  phone text not null default '',
  email text,
  account_type account_type not null default 'debtor',
  tax_id text,
  commercial_registration text,
  shop_name text,
  activity_type text,
  shop_location text,
  shop_description text,
  whatsapp_enabled boolean not null default true,
  ai_enabled boolean not null default false,
  trust_score int not null default 50 check (trust_score between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ── QR Tokens ──────────────────────────────────────────────────
create table public.qr_tokens (
  token uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

-- ── Groups ─────────────────────────────────────────────────────
create table public.groups (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade,
  name text not null,
  description text,
  created_at timestamptz not null default now()
);

create table public.group_members (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.groups(id) on delete cascade,
  user_id uuid not null references public.profiles(id) on delete cascade,
  status group_member_status not null default 'pending',
  created_at timestamptz not null default now(),
  accepted_at timestamptz,
  unique (group_id, user_id)
);

-- ── Debts ──────────────────────────────────────────────────────
create table public.debts (
  id uuid primary key default gen_random_uuid(),
  creditor_id uuid not null references public.profiles(id) on delete cascade,
  debtor_id uuid references public.profiles(id) on delete set null,
  debtor_name text not null,
  amount numeric(12, 2) not null check (amount > 0),
  currency char(3) not null default 'SAR',
  description text not null,
  due_date date not null,
  status debt_status not null default 'waiting_for_confirmation',
  invoice_url text,
  notes text,
  group_id uuid references public.groups(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  confirmed_at timestamptz,
  paid_at timestamptz
);

create table public.debt_events (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null references public.debts(id) on delete cascade,
  actor_id uuid references public.profiles(id) on delete set null,
  event_type text not null,
  message text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table public.payment_confirmations (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null unique references public.debts(id) on delete cascade,
  debtor_id uuid not null references public.profiles(id) on delete cascade,
  creditor_id uuid not null references public.profiles(id) on delete cascade,
  status text not null,
  note text,
  requested_at timestamptz not null default now(),
  confirmed_at timestamptz
);

-- ── Attachments ────────────────────────────────────────────────
create table public.attachments (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null references public.debts(id) on delete cascade,
  uploader_id uuid not null references public.profiles(id) on delete cascade,
  attachment_type attachment_type not null,
  file_name text not null,
  content_type text,
  storage_path text not null,
  public_url text,
  created_at timestamptz not null default now()
);

-- ── Notifications ──────────────────────────────────────────────
create table public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  notification_type text not null,
  title text not null,
  body text not null,
  debt_id uuid references public.debts(id) on delete cascade,
  read_at timestamptz,
  whatsapp_attempted boolean not null default false,
  created_at timestamptz not null default now()
);

-- ── Trust Score Events ─────────────────────────────────────────
create table public.trust_score_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  delta int not null,
  score_after int not null check (score_after between 0 and 100),
  reason text not null,
  debt_id uuid references public.debts(id) on delete set null,
  created_at timestamptz not null default now()
);

-- ── Group Settlements ──────────────────────────────────────────
create table public.group_settlements (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.groups(id) on delete cascade,
  payer_id uuid not null references public.profiles(id) on delete cascade,
  debtor_id uuid not null references public.profiles(id) on delete cascade,
  amount numeric(12, 2) not null check (amount > 0),
  currency char(3) not null default 'SAR',
  note text,
  created_at timestamptz not null default now()
);

-- ── Indexes ────────────────────────────────────────────────────
create index debts_creditor_id_idx on public.debts (creditor_id);
create index debts_debtor_id_idx on public.debts (debtor_id);
create index debts_status_due_date_idx on public.debts (status, due_date);
create index notifications_user_id_idx on public.notifications (user_id, read_at);
create index group_members_user_id_idx on public.group_members (user_id, status);

-- ── Row Level Security ─────────────────────────────────────────
alter table public.profiles enable row level security;
alter table public.debts enable row level security;
alter table public.notifications enable row level security;
alter table public.qr_tokens enable row level security;
alter table public.groups enable row level security;
alter table public.group_members enable row level security;
alter table public.debt_events enable row level security;
alter table public.payment_confirmations enable row level security;
alter table public.attachments enable row level security;
alter table public.trust_score_events enable row level security;
alter table public.group_settlements enable row level security;

-- Profiles: users can read/update their own profile, creditors can read debtor profiles
create policy "Users can view own profile" on public.profiles
  for select using (auth.uid() = id);
create policy "Users can update own profile" on public.profiles
  for update using (auth.uid() = id);
create policy "Users can insert own profile" on public.profiles
  for insert with check (auth.uid() = id);
create policy "Creditors can view debtor profiles" on public.profiles
  for select using (
    id in (select debtor_id from public.debts where creditor_id = auth.uid())
    or id in (select creditor_id from public.debts where debtor_id = auth.uid())
  );

-- Debts: users can see debts where they are creditor or debtor
create policy "Users can view own debts" on public.debts
  for select using (auth.uid() = creditor_id or auth.uid() = debtor_id);
create policy "Creditors can create debts" on public.debts
  for insert with check (auth.uid() = creditor_id);
create policy "Parties can update debts" on public.debts
  for update using (auth.uid() = creditor_id or auth.uid() = debtor_id);

-- Notifications: users can see their own
create policy "Users can view own notifications" on public.notifications
  for select using (auth.uid() = user_id);
create policy "System can insert notifications" on public.notifications
  for insert with check (true);
create policy "Users can update own notifications" on public.notifications
  for update using (auth.uid() = user_id);

-- QR Tokens: users manage their own
create policy "Users can manage own QR tokens" on public.qr_tokens
  for all using (auth.uid() = user_id);

-- Groups: owner and members can view
create policy "Users can view own groups" on public.groups
  for select using (
    auth.uid() = owner_id
    or id in (select group_id from public.group_members where user_id = auth.uid())
  );
create policy "Users can create groups" on public.groups
  for insert with check (auth.uid() = owner_id);

-- Group members
create policy "Users can view group members" on public.group_members
  for select using (
    group_id in (select id from public.groups where owner_id = auth.uid())
    or user_id = auth.uid()
  );

-- Debt events: visible to debt parties
create policy "Debt parties can view events" on public.debt_events
  for select using (
    debt_id in (select id from public.debts where creditor_id = auth.uid() or debtor_id = auth.uid())
  );

-- Payment confirmations
create policy "Debt parties can view payment confirmations" on public.payment_confirmations
  for select using (auth.uid() = debtor_id or auth.uid() = creditor_id);
create policy "Debtors can request payment" on public.payment_confirmations
  for insert with check (auth.uid() = debtor_id);
create policy "Creditors can confirm payment" on public.payment_confirmations
  for update using (auth.uid() = creditor_id);

-- Attachments: visible to debt parties
create policy "Debt parties can view attachments" on public.attachments
  for select using (
    debt_id in (select id from public.debts where creditor_id = auth.uid() or debtor_id = auth.uid())
  );

-- Trust score events: users see their own
create policy "Users can view own trust events" on public.trust_score_events
  for select using (auth.uid() = user_id);

-- Group settlements
create policy "Users can view own settlements" on public.group_settlements
  for select using (auth.uid() = payer_id or auth.uid() = debtor_id);

-- ── Auto-create profile on signup ──────────────────────────────
-- This trigger creates a profile row when a new user signs up via GoTrue
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = ''
as $$
begin
  insert into public.profiles (id, name, phone, email, account_type)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', ''),
    coalesce(new.raw_user_meta_data->>'phone', ''),
    new.email,
    coalesce((new.raw_user_meta_data->>'account_type')::public.account_type, 'debtor')
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ── Storage bucket for attachments ─────────────────────────────
insert into storage.buckets (id, name, public)
values ('thabetha-attachments', 'thabetha-attachments', false)
on conflict (id) do nothing;
