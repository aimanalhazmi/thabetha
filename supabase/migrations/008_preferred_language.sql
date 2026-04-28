-- ── 008: Add preferred_language to profiles ────────────────────────────────
-- Stores the user's language preference (ar | en) on the profile row so it
-- is synced across devices for signed-in users. Existing rows default to 'ar'
-- (Arabic-first per constitution §V).

alter table public.profiles
  add column preferred_language text not null default 'ar'
  check (preferred_language in ('ar', 'en'));

-- Update the new-user trigger to seed the column from auth metadata when present.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer as $$
begin
  insert into public.profiles (id, name, phone, email, account_type, preferred_language)
  values (
    new.id,
    coalesce(new.raw_user_meta_data->>'name', ''),
    coalesce(new.raw_user_meta_data->>'phone', ''),
    new.email,
    coalesce((new.raw_user_meta_data->>'account_type')::public.account_type, 'debtor'),
    coalesce(new.raw_user_meta_data->>'preferred_language', 'ar')
  );
  return new;
end;
$$;
