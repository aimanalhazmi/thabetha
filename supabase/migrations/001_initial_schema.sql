create extension if not exists pgcrypto;

create type account_type as enum ('individual', 'business');
create type debt_status as enum ('pending_confirmation', 'active', 'overdue', 'payment_pending_confirmation', 'paid', 'rejected', 'change_requested');
create type attachment_type as enum ('invoice', 'voice_note', 'other');
create type group_member_status as enum ('pending', 'accepted');

-- Credential store (replaces GoTrue / auth.users)
create table public.users (
  id uuid primary key default gen_random_uuid(),
  email text not null unique,
  password_hash text not null,
  name text not null default '',
  phone text not null default '',
  created_at timestamptz not null default now()
);

create table public.profiles (
  id uuid primary key references public.users(id) on delete cascade,
  name text not null,
  phone text not null,
  email text,
  account_type account_type not null default 'individual',
  tax_id text,
  commercial_registration text,
  whatsapp_enabled boolean not null default true,
  ai_enabled boolean not null default false,
  trust_score int not null default 50 check (trust_score between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.business_profiles (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null unique references public.profiles(id) on delete cascade,
  shop_name text not null,
  activity_type text not null,
  location text not null,
  description text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table public.qr_tokens (
  token uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

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

create table public.debts (
  id uuid primary key default gen_random_uuid(),
  creditor_id uuid not null references public.profiles(id) on delete cascade,
  debtor_id uuid references public.profiles(id) on delete set null,
  debtor_name text not null,
  amount numeric(12, 2) not null check (amount > 0),
  currency char(3) not null,
  description text not null,
  due_date date not null,
  status debt_status not null default 'pending_confirmation',
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

create table public.merchant_notification_preferences (
  user_id uuid not null references public.profiles(id) on delete cascade,
  merchant_id uuid not null references public.profiles(id) on delete cascade,
  whatsapp_enabled boolean not null default true,
  updated_at timestamptz not null default now(),
  primary key (user_id, merchant_id)
);

create table public.trust_score_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  delta int not null,
  score_after int not null check (score_after between 0 and 100),
  reason text not null,
  debt_id uuid references public.debts(id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.group_settlements (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.groups(id) on delete cascade,
  payer_id uuid not null references public.profiles(id) on delete cascade,
  debtor_id uuid not null references public.profiles(id) on delete cascade,
  amount numeric(12, 2) not null check (amount > 0),
  currency char(3) not null,
  note text,
  created_at timestamptz not null default now()
);

create index debts_creditor_id_idx on public.debts (creditor_id);
create index debts_debtor_id_idx on public.debts (debtor_id);
create index debts_status_due_date_idx on public.debts (status, due_date);
create index notifications_user_id_idx on public.notifications (user_id, read_at);
create index group_members_user_id_idx on public.group_members (user_id, status);
