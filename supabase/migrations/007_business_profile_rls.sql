-- business_profiles had RLS enabled in 001 but no policies, which blocks all
-- non-superuser access. Mirror the simple owner-scoped policy used for profiles.
drop policy if exists "Allow business profile owner access" on public.business_profiles;
create policy "Allow business profile owner access"
  on public.business_profiles for all
  using (auth.uid() = owner_id)
  with check (auth.uid() = owner_id);
