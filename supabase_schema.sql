-- SRM Lost & Found (Trichy Campus) - Supabase schema
-- Run the whole file once in Supabase Dashboard > SQL Editor. Safe to re-run.

-- ============ TABLES ============
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null check (char_length(full_name) between 2 and 80),
  department text,
  register_number text,
  student_code text unique,
  role text not null default 'student' check (role in ('student','admin')),
  created_at timestamptz not null default now()
);

-- Student identity fields (safe to run on an existing project too).
alter table public.profiles add column if not exists register_number text;
create unique index if not exists profiles_register_number_uidx
  on public.profiles (upper(register_number)) where register_number is not null;

-- Public-safe profile projection. The full register number is never exposed in item cards or chat.
create or replace view public.profiles_public
with (security_barrier = true)
as
select id, full_name, department, student_code,
       case when register_number is null or length(register_number) < 4 then '••••'
            else '••••' || right(register_number, 4) end as register_number_masked
from public.profiles;

create table if not exists public.items (
  id uuid primary key default gen_random_uuid(),
  reporter_id uuid not null references public.profiles(id) on delete cascade,
  type text not null check (type in ('lost','found')),
  title text not null check (char_length(title) between 3 and 80),
  category text not null,
  description text not null check (char_length(description) between 10 and 1000),
  location text not null,
  event_date date not null,
  photo_url text,
  status text not null default 'open' check (status in ('open','resolved','removed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists items_created_idx on public.items (created_at desc);
create index if not exists items_filter_idx on public.items (type, status, category);
create index if not exists items_reporter_idx on public.items (reporter_id);

create table if not exists public.claim_requests (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items(id) on delete cascade,
  claimant_id uuid not null references public.profiles(id) on delete cascade,
  message text not null check (char_length(message) between 10 and 500),
  status text not null default 'pending' check (status in ('pending','approved','rejected')),
  owner_note text check (char_length(owner_note) <= 300),
  created_at timestamptz not null default now(),
  responded_at timestamptz,
  unique (item_id, claimant_id)
);
create index if not exists claims_item_idx on public.claim_requests (item_id);
create index if not exists claims_claimant_idx on public.claim_requests (claimant_id);

create table if not exists public.content_reports (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items(id) on delete cascade,
  reporter_id uuid not null references public.profiles(id) on delete cascade,
  reason text not null check (char_length(reason) between 5 and 300),
  resolved boolean not null default false,
  created_at timestamptz not null default now(),
  unique (item_id, reporter_id)
);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  title text not null,
  body text,
  item_id uuid references public.items(id) on delete cascade,
  is_read boolean not null default false,
  created_at timestamptz not null default now()
);
create index if not exists notes_user_idx on public.notifications (user_id, created_at desc);


-- Private one-to-one student messages. Only sender and receiver can read a row.
create table if not exists public.direct_messages (
  id uuid primary key default gen_random_uuid(),
  sender_id uuid not null references public.profiles(id) on delete cascade,
  receiver_id uuid not null references public.profiles(id) on delete cascade,
  message text not null check (char_length(message) between 1 and 1000),
  created_at timestamptz not null default now(),
  constraint direct_messages_no_self check (sender_id <> receiver_id)
);
create index if not exists direct_messages_sender_idx
  on public.direct_messages(sender_id, created_at desc);
create index if not exists direct_messages_receiver_idx
  on public.direct_messages(receiver_id, created_at desc);

-- ============ HELPER FUNCTIONS ============
create or replace function public.is_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.profiles where id = auth.uid() and role = 'admin');
$$;

-- Student app codes: random, non-sensitive identifiers used in QR codes.
alter table public.profiles add column if not exists student_code text;
create unique index if not exists profiles_student_code_uidx
  on public.profiles(student_code) where student_code is not null;

create or replace function public.make_student_code()
returns text
language plpgsql
volatile
set search_path = public, pg_temp
as $$
declare candidate text;
begin
  loop
    -- gen_random_uuid() is built into supported PostgreSQL versions; this avoids
    -- depending on pgcrypto being installed in a particular schema/search_path.
    candidate := 'STU-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8));
    exit when not exists (select 1 from public.profiles where student_code = candidate);
  end loop;
  return candidate;
end $$;

update public.profiles set student_code = public.make_student_code() where student_code is null;

-- Create a profile automatically when a user signs up.
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, full_name, department, register_number, student_code)
  values (
    new.id,
    left(coalesce(nullif(trim(new.raw_user_meta_data->>'full_name'), ''), split_part(new.email, '@', 1)), 80),
    nullif(trim(new.raw_user_meta_data->>'department'), ''),
    upper(nullif(trim(new.raw_user_meta_data->>'register_number'), '')),
    public.make_student_code()
  )
  on conflict (id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- Students cannot promote themselves to admin.
create or replace function public.profiles_guard()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if auth.uid() is not null and not public.is_admin() then
    new.role := old.role;
  end if;
  return new;
end $$;
drop trigger if exists profiles_guard_trg on public.profiles;
create trigger profiles_guard_trg before update on public.profiles
  for each row execute function public.profiles_guard();

-- Items: owners cannot change owner/type, un-remove, or self-remove (they can delete instead).
create or replace function public.items_guard()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  new.updated_at := now();
  if auth.uid() is not null and not public.is_admin() then
    new.reporter_id := old.reporter_id;
    new.type := old.type;
    if old.status = 'removed' then new.status := 'removed'; end if;
    if new.status = 'removed' then new.status := old.status; end if;
  end if;
  return new;
end $$;
drop trigger if exists items_guard_trg on public.items;
create trigger items_guard_trg before update on public.items
  for each row execute function public.items_guard();

-- ============ NOTIFICATION TRIGGERS ============
create or replace function public.notify_claim_created()
returns trigger language plpgsql security definer set search_path = public as $$
declare it public.items;
begin
  select * into it from public.items where id = new.item_id;
  insert into public.notifications (user_id, title, body, item_id)
  values (it.reporter_id, 'New claim request', 'Someone sent a claim request for "' || it.title || '".', it.id);
  return new;
end $$;
drop trigger if exists claim_created_trg on public.claim_requests;
create trigger claim_created_trg after insert on public.claim_requests
  for each row execute function public.notify_claim_created();

create or replace function public.notify_claim_updated()
returns trigger language plpgsql security definer set search_path = public as $$
declare it public.items;
begin
  if new.status is distinct from old.status then
    select * into it from public.items where id = new.item_id;
    insert into public.notifications (user_id, title, body, item_id)
    values (new.claimant_id, 'Claim ' || new.status,
            'Your claim request for "' || it.title || '" was ' || new.status || '.', it.id);
  end if;
  return new;
end $$;
drop trigger if exists claim_updated_trg on public.claim_requests;
create trigger claim_updated_trg after update on public.claim_requests
  for each row execute function public.notify_claim_updated();

create or replace function public.notify_item_status()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  if new.status is distinct from old.status then
    if new.status = 'resolved' then
      insert into public.notifications (user_id, title, body, item_id)
      select c.claimant_id, 'Report resolved', '"' || new.title || '" was marked as resolved.', new.id
      from public.claim_requests c where c.item_id = new.id and c.status = 'pending';
    elsif new.status = 'removed' then
      insert into public.notifications (user_id, title, body, item_id)
      values (new.reporter_id, 'Report removed by moderators',
              'Your report "' || new.title || '" was removed for violating the safety guidelines.', new.id);
    end if;
  end if;
  return new;
end $$;
drop trigger if exists item_status_trg on public.items;
create trigger item_status_trg after update on public.items
  for each row execute function public.notify_item_status();

-- ============ PRIVILEGES (column-level where it matters) ============
revoke all on public.profiles, public.items, public.claim_requests, public.content_reports, public.notifications, public.direct_messages from anon, authenticated;

grant select on public.profiles to authenticated;
grant select on public.profiles_public to authenticated;
grant update (full_name, department, register_number) on public.profiles to authenticated;
grant select, insert on public.direct_messages to authenticated;

grant select, insert, update, delete on public.items to authenticated;

grant select on public.claim_requests to authenticated;
grant insert (item_id, claimant_id, message) on public.claim_requests to authenticated;
grant update (status, owner_note, responded_at) on public.claim_requests to authenticated;

grant select on public.content_reports to authenticated;
grant insert (item_id, reporter_id, reason) on public.content_reports to authenticated;
grant update (resolved) on public.content_reports to authenticated;

grant select on public.notifications to authenticated;
grant update (is_read) on public.notifications to authenticated;

-- ============ ROW LEVEL SECURITY ============
alter table public.profiles enable row level security;
alter table public.items enable row level security;
alter table public.claim_requests enable row level security;
alter table public.content_reports enable row level security;
alter table public.notifications enable row level security;
alter table public.direct_messages enable row level security;

-- profiles
drop policy if exists "profiles read" on public.profiles;
drop policy if exists "profiles read own or admin" on public.profiles;
create policy "profiles read own or admin" on public.profiles for select to authenticated
  using (id = auth.uid() or public.is_admin());
drop policy if exists "profiles update own" on public.profiles;
create policy "profiles update own" on public.profiles for update to authenticated
  using (id = auth.uid() or public.is_admin()) with check (id = auth.uid() or public.is_admin());

-- items
drop policy if exists "items read" on public.items;
create policy "items read" on public.items for select to authenticated
  using (status <> 'removed' or reporter_id = auth.uid() or public.is_admin());
drop policy if exists "items insert own" on public.items;
create policy "items insert own" on public.items for insert to authenticated
  with check (reporter_id = auth.uid() and status = 'open');
drop policy if exists "items update own or admin" on public.items;
create policy "items update own or admin" on public.items for update to authenticated
  using (reporter_id = auth.uid() or public.is_admin())
  with check (reporter_id = auth.uid() or public.is_admin());
drop policy if exists "items delete own or admin" on public.items;
create policy "items delete own or admin" on public.items for delete to authenticated
  using (reporter_id = auth.uid() or public.is_admin());

-- claim requests: visible only to the claimant, the item's owner, and admins
drop policy if exists "claims read" on public.claim_requests;
create policy "claims read" on public.claim_requests for select to authenticated
  using (
    claimant_id = auth.uid() or public.is_admin()
    or exists (select 1 from public.items i where i.id = item_id and i.reporter_id = auth.uid())
  );
drop policy if exists "claims insert" on public.claim_requests;
create policy "claims insert" on public.claim_requests for insert to authenticated
  with check (
    claimant_id = auth.uid() and status = 'pending'
    and exists (select 1 from public.items i
                where i.id = item_id and i.reporter_id <> auth.uid() and i.status = 'open')
  );
drop policy if exists "claims owner respond" on public.claim_requests;
create policy "claims owner respond" on public.claim_requests for update to authenticated
  using (exists (select 1 from public.items i where i.id = item_id and i.reporter_id = auth.uid()))
  with check (exists (select 1 from public.items i where i.id = item_id and i.reporter_id = auth.uid()));

-- content reports (moderation flags)
drop policy if exists "flags insert" on public.content_reports;
create policy "flags insert" on public.content_reports for insert to authenticated
  with check (reporter_id = auth.uid());
drop policy if exists "flags read" on public.content_reports;
create policy "flags read" on public.content_reports for select to authenticated
  using (reporter_id = auth.uid() or public.is_admin());
drop policy if exists "flags admin update" on public.content_reports;
create policy "flags admin update" on public.content_reports for update to authenticated
  using (public.is_admin()) with check (public.is_admin());

-- notifications: own only (rows are created by the security-definer triggers above)
drop policy if exists "notes read own" on public.notifications;
create policy "notes read own" on public.notifications for select to authenticated using (user_id = auth.uid());
drop policy if exists "notes update own" on public.notifications;
create policy "notes update own" on public.notifications for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ============ STORAGE (item photos) ============
-- Public bucket: anyone with a photo URL can view it. Files are stored under <user_id>/<random>.jpg.
-- Tell students never to photograph IDs/cards with visible numbers (see Safety page).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('item-photos', 'item-photos', true, 5242880, array['image/jpeg','image/png','image/webp'])
on conflict (id) do update
  set public = true, file_size_limit = 5242880,
      allowed_mime_types = array['image/jpeg','image/png','image/webp'];

drop policy if exists "photos upload own folder" on storage.objects;
create policy "photos upload own folder" on storage.objects for insert to authenticated
  with check (bucket_id = 'item-photos' and (storage.foldername(name))[1] = auth.uid()::text);
drop policy if exists "photos read" on storage.objects;
create policy "photos read" on storage.objects for select to authenticated
  using (bucket_id = 'item-photos');
drop policy if exists "photos delete own or admin" on storage.objects;
create policy "photos delete own or admin" on storage.objects for delete to authenticated
  using (bucket_id = 'item-photos' and ((storage.foldername(name))[1] = auth.uid()::text or public.is_admin()));

-- ============ MAKE YOURSELF ADMIN (run manually after you have registered) ============
-- update public.profiles set role = 'admin'
--   where id = (select id from auth.users where email = 'you@srmist.edu.in');


-- direct messages: a user may only read messages they sent or received,
-- and may only send a message as themselves to another student.
drop policy if exists "direct messages participants read" on public.direct_messages;
create policy "direct messages participants read" on public.direct_messages
  for select to authenticated
  using (sender_id = auth.uid() or receiver_id = auth.uid());

drop policy if exists "direct messages sender insert" on public.direct_messages;
create policy "direct messages sender insert" on public.direct_messages
  for insert to authenticated
  with check (sender_id = auth.uid() and receiver_id <> auth.uid());


-- ============ FUNCTION PERMISSION HARDENING ============
-- Helper used by authenticated RLS policies. SECURITY DEFINER avoids recursive profile-policy evaluation;
-- the function has a fixed search_path and exposes only the current user's admin boolean.
create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select exists (
    select 1 from public.profiles
    where id = auth.uid() and role = 'admin'
  );
$$;

-- Fix mutable search_path on the student-code generator.
create or replace function public.make_student_code()
returns text
language plpgsql
volatile
set search_path = public, pg_temp
as $$
declare candidate text;
begin
  loop
    candidate := 'STU-' || upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8));
    exit when not exists (
      select 1 from public.profiles where student_code = candidate
    );
  end loop;
  return candidate;
end $$;

-- Trigger-only functions must not be callable through the public PostgREST RPC API.
revoke execute on function public.make_student_code() from public, anon, authenticated;
revoke execute on function public.handle_new_user() from public, anon, authenticated;
revoke execute on function public.profiles_guard() from public, anon, authenticated;
revoke execute on function public.items_guard() from public, anon, authenticated;
revoke execute on function public.notify_claim_created() from public, anon, authenticated;
revoke execute on function public.notify_claim_updated() from public, anon, authenticated;
revoke execute on function public.notify_item_status() from public, anon, authenticated;

-- Authenticated users need this helper for the admin-aware RLS policies.
revoke execute on function public.is_admin() from public, anon;
grant execute on function public.is_admin() to authenticated;

-- Remove access to a legacy helper if it exists in an older database.
do $$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    execute 'revoke execute on function public.rls_auto_enable() from public, anon, authenticated';
  end if;
end;
$$;
