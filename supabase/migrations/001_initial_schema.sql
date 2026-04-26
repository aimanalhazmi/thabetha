-- Thabetha Schema — Updated for 2026
create extension if not exists pgcrypto;

-- ── Enums ──────────────────────────────────────────────────────
create type account_type as enum ('creditor', 'debtor', 'both', 'business');
create type debt_status as enum (
  'pending_confirmation',
  'active',
  'paid',
  'overdue',
  'edit_requested',
  'payment_pending_confirmation',
  'cancelled'
);
create type attachment_type as enum ('invoice', 'voice_note', 'other');
create type group_member_status as enum ('pending', 'accepted');

-- ── Profiles ───────────────────────────────────────────────────
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  name text not null,
  phone text not null default '',
  email text,
  account_type account_type not null default 'debtor',
  tax_id text,
  commercial_registration text,
  whatsapp_enabled boolean not null default true,
  ai_enabled boolean not null default false,
  commitment_score int not null default 50 check (commitment_score between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ── Business Profiles ──────────────────────────────────────────
create table public.business_profiles (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references public.profiles(id) on delete cascade unique,
  shop_name text,
  activity_type text,
  location text,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- ── Merchant Notification Preferences ──────────────────────────
create table public.merchant_notification_preferences (
  user_id uuid references public.profiles(id) on delete cascade,
  merchant_id uuid references public.profiles(id) on delete cascade,
  whatsapp_enabled boolean not null default true,
  updated_at timestamptz not null default now(),
  primary key (user_id, merchant_id)
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
  status debt_status not null default 'pending_confirmation',
  invoice_url text,
  notes text,
  group_id uuid, -- Reference to groups(id)
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  confirmed_at timestamptz,
  paid_at timestamptz
);

-- ── Additional Tables (simplified for brevity) ──────────────────
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

create table public.debt_events (
  id uuid primary key default gen_random_uuid(),
  debt_id uuid not null references public.debts(id) on delete cascade,
  actor_id uuid references public.profiles(id) on delete set null,
  event_type text not null,
  message text,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table public.commitment_score_events (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  delta int not null,
  score_after int not null check (score_after between 0 and 100),
  reason text not null,
  debt_id uuid,
  created_at timestamptz not null default now()
);

-- ── RLS & Security ─────────────────────────────────────────────
alter table public.profiles enable row level security;
alter table public.business_profiles enable row level security;
alter table public.debts enable row level security;

-- Policies (Simplified)
create policy "Allow profile access" on public.profiles for all using (auth.uid() = id);
create policy "Allow debt access" on public.debts for all using (auth.uid() = creditor_id or auth.uid() = debtor_id);

-- ── Trigger: Auto-create profile ──────────────────────────────
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, name, email)
  values (new.id, coalesce(new.raw_user_meta_data->>'name', 'User'), new.email);
  return new;
end;
$$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- ── Storage bucket for attachments ─────────────────────────────
insert into storage.buckets (id, name, public)
values ('thabetha-attachments', 'thabetha-attachments', false)
on conflict (id) do nothing;
