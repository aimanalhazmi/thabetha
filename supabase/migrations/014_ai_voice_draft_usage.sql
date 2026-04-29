-- Phase 12: AI voice-to-debt draft daily usage counters.

create table if not exists public.ai_usage_records (
  user_id uuid not null references public.profiles(id) on delete cascade,
  usage_date date not null,
  feature text not null,
  count integer not null default 0 check (count >= 0),
  limit_value integer not null check (limit_value > 0),
  updated_at timestamptz not null default now(),
  primary key (user_id, usage_date, feature)
);

alter table public.ai_usage_records enable row level security;

drop policy if exists "ai_usage_records_own_select" on public.ai_usage_records;
create policy "ai_usage_records_own_select"
on public.ai_usage_records
for select
using (auth.uid() = user_id);

drop policy if exists "ai_usage_records_own_insert" on public.ai_usage_records;
create policy "ai_usage_records_own_insert"
on public.ai_usage_records
for insert
with check (auth.uid() = user_id);

drop policy if exists "ai_usage_records_own_update" on public.ai_usage_records;
create policy "ai_usage_records_own_update"
on public.ai_usage_records
for update
using (auth.uid() = user_id)
with check (auth.uid() = user_id);
