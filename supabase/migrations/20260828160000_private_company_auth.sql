create table private.signup_email_domains (
  domain text primary key check (domain = lower(domain) and domain !~ '@'),
  created_at timestamptz not null default timezone('utc', now())
);

create table private.blocked_signup_local_parts (
  local_part text primary key check (local_part = lower(local_part) and local_part !~ '@'),
  created_at timestamptz not null default timezone('utc', now())
);

insert into private.signup_email_domains (domain)
values ('mellanni.com');

insert into private.blocked_signup_local_parts (local_part)
values
  ('admin'),
  ('contact'),
  ('hello'),
  ('help'),
  ('info'),
  ('marketing'),
  ('no-reply'),
  ('noreply'),
  ('orders'),
  ('returns'),
  ('sales'),
  ('support'),
  ('team');

revoke all on table private.signup_email_domains from public, anon, authenticated;
revoke all on table private.blocked_signup_local_parts from public, anon, authenticated;

create table public.members (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null check (email = lower(email)),
  role text not null default 'reader' check (role in ('reader', 'admin')),
  active boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index members_email_idx on public.members (lower(email));

create trigger members_set_updated_at
before update on public.members
for each row execute function public.set_updated_at();

create or replace function private.is_allowed_mellanni_identity(
  candidate_email text,
  app_metadata jsonb
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    lower(btrim(coalesce(candidate_email, ''))) ~ '^[^@]+@[^@]+$'
    and (
      lower(coalesce(app_metadata ->> 'provider', '')) = 'google'
      or coalesce(app_metadata -> 'providers', '[]'::jsonb) ? 'google'
    )
    and exists (
      select 1
      from private.signup_email_domains
      where domain = split_part(lower(btrim(candidate_email)), '@', 2)
    )
    and not exists (
      select 1
      from private.blocked_signup_local_parts
      where local_part = split_part(lower(btrim(candidate_email)), '@', 1)
    );
$$;

revoke all on function private.is_allowed_mellanni_identity(text, jsonb) from public;

create or replace function public.hook_restrict_signup_by_email_domain(event jsonb)
returns jsonb
language plpgsql
stable
security definer
set search_path = ''
as $$
begin
  if private.is_allowed_mellanni_identity(
    event -> 'user' ->> 'email',
    coalesce(event -> 'user' -> 'app_metadata', '{}'::jsonb)
  ) then
    return '{}'::jsonb;
  end if;

  return jsonb_build_object(
    'error', jsonb_build_object(
      'http_code', 403,
      'message', 'Use an active personal Mellanni Google account.'
    )
  );
end;
$$;

revoke all on function public.hook_restrict_signup_by_email_domain(jsonb)
from public, anon, authenticated;
grant usage on schema public to supabase_auth_admin;
grant execute on function public.hook_restrict_signup_by_email_domain(jsonb)
to supabase_auth_admin;

create or replace function private.provision_mellanni_member()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if private.is_allowed_mellanni_identity(new.email, new.raw_app_meta_data) then
    insert into public.members (user_id, email, role)
    values (
      new.id,
      lower(new.email),
      case when lower(new.email) = 'sergey@mellanni.com' then 'admin' else 'reader' end
    )
    on conflict (user_id) do update
    set email = excluded.email;
  else
    update public.members
    set active = false
    where user_id = new.id;
  end if;

  return new;
end;
$$;

revoke all on function private.provision_mellanni_member() from public;

create trigger auth_users_provision_mellanni_member
after insert or update of email, raw_app_meta_data on auth.users
for each row execute function private.provision_mellanni_member();

insert into public.members (user_id, email, role)
select
  id,
  lower(email),
  case when lower(email) = 'sergey@mellanni.com' then 'admin' else 'reader' end
from auth.users
where
  email is not null
  and private.is_allowed_mellanni_identity(email, raw_app_meta_data)
on conflict (user_id) do update
set
  email = excluded.email,
  role = excluded.role;

create or replace function private.jwt_uses_oauth()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select exists (
    select 1
    from jsonb_array_elements(coalesce(auth.jwt() -> 'amr', '[]'::jsonb)) as entry
    where entry ->> 'method' = 'oauth'
  );
$$;

revoke all on function private.jwt_uses_oauth() from public;
grant execute on function private.jwt_uses_oauth() to authenticated;

create or replace function private.is_active_mellanni_member()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    private.jwt_uses_oauth()
    and exists (
      select 1
      from public.members
      where user_id = auth.uid() and active
    );
$$;

revoke all on function private.is_active_mellanni_member() from public;
grant execute on function private.is_active_mellanni_member() to authenticated;

create or replace function private.is_mellanni_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select
    private.jwt_uses_oauth()
    and exists (
      select 1
      from public.members
      where user_id = auth.uid() and active and role = 'admin'
    );
$$;

revoke all on function private.is_mellanni_admin() from public;
grant execute on function private.is_mellanni_admin() to authenticated;

create table public.digest_private_bodies (
  digest_id uuid primary key references public.digests(id) on delete cascade,
  private_body jsonb not null check (jsonb_typeof(private_body) = 'object'),
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

insert into public.digest_private_bodies (digest_id, private_body)
select id, private_body
from public.digests;

alter table public.digests drop column private_body;

create trigger digest_private_bodies_set_updated_at
before update on public.digest_private_bodies
for each row execute function public.set_updated_at();

create or replace function public.upsert_digest_with_private_body(
  p_slug text,
  p_published_on date,
  p_status text,
  p_title text,
  p_summary text,
  p_body jsonb,
  p_private_body jsonb,
  p_published_at timestamptz
)
returns setof public.digests
language plpgsql
security definer
set search_path = ''
as $$
declare
  saved_digest public.digests;
begin
  insert into public.digests (
    slug, published_on, status, title, summary, body, published_at
  )
  values (
    p_slug, p_published_on, p_status, p_title, p_summary, p_body, p_published_at
  )
  on conflict (slug) do update
  set
    published_on = excluded.published_on,
    status = excluded.status,
    title = excluded.title,
    summary = excluded.summary,
    body = excluded.body,
    published_at = excluded.published_at
  returning * into saved_digest;

  insert into public.digest_private_bodies (digest_id, private_body)
  values (saved_digest.id, p_private_body)
  on conflict (digest_id) do update
  set private_body = excluded.private_body;

  return next saved_digest;
end;
$$;

revoke all on function public.upsert_digest_with_private_body(
  text, date, text, text, text, jsonb, jsonb, timestamptz
) from public, anon, authenticated;
grant execute on function public.upsert_digest_with_private_body(
  text, date, text, text, text, jsonb, jsonb, timestamptz
) to service_role;

alter table public.members enable row level security;
alter table public.digest_private_bodies enable row level security;

revoke all on table public.members from anon, authenticated;
revoke all on table public.digest_private_bodies from anon, authenticated;
revoke all on table public.sources from anon, authenticated;
revoke all on table public.digests from anon, authenticated;
revoke all on table public.runs from anon, authenticated;

grant all on table public.members to service_role;
grant all on table public.digest_private_bodies to service_role;

grant select on table public.members to authenticated;
grant select, insert, update, delete on table public.sources to authenticated;
grant select, insert, update, delete on table public.digests to authenticated;
grant select, insert, update, delete on table public.runs to authenticated;
grant select on table public.digest_private_bodies to authenticated;

drop policy if exists "Published digests are public" on public.digests;
drop policy if exists "Admin reads all sources" on public.sources;
drop policy if exists "Admin creates sources" on public.sources;
drop policy if exists "Admin updates sources" on public.sources;
drop policy if exists "Admin deletes sources" on public.sources;
drop policy if exists "Admin reads all digests" on public.digests;
drop policy if exists "Admin creates digests" on public.digests;
drop policy if exists "Admin updates digests" on public.digests;
drop policy if exists "Admin deletes digests" on public.digests;
drop policy if exists "Admin reads runs" on public.runs;
drop policy if exists "Admin creates runs" on public.runs;
drop policy if exists "Admin updates runs" on public.runs;
drop policy if exists "Admin deletes runs" on public.runs;

create policy "Members read own membership"
on public.members for select
to authenticated
using (
  user_id = auth.uid()
  and active
  and (select private.jwt_uses_oauth())
);

create policy "Active members read published digests"
on public.digests for select
to authenticated
using (
  status = 'published'
  and (select private.is_active_mellanni_member())
);

create policy "Admin reads all sources"
on public.sources for select
to authenticated
using ((select private.is_mellanni_admin()));

create policy "Admin creates sources"
on public.sources for insert
to authenticated
with check ((select private.is_mellanni_admin()));

create policy "Admin updates sources"
on public.sources for update
to authenticated
using ((select private.is_mellanni_admin()))
with check ((select private.is_mellanni_admin()));

create policy "Admin deletes sources"
on public.sources for delete
to authenticated
using ((select private.is_mellanni_admin()));

create policy "Admin reads all digests"
on public.digests for select
to authenticated
using ((select private.is_mellanni_admin()));

create policy "Admin creates digests"
on public.digests for insert
to authenticated
with check ((select private.is_mellanni_admin()));

create policy "Admin updates digests"
on public.digests for update
to authenticated
using ((select private.is_mellanni_admin()))
with check ((select private.is_mellanni_admin()));

create policy "Admin deletes digests"
on public.digests for delete
to authenticated
using ((select private.is_mellanni_admin()));

create policy "Admin reads private digest bodies"
on public.digest_private_bodies for select
to authenticated
using ((select private.is_mellanni_admin()));

create policy "Admin reads runs"
on public.runs for select
to authenticated
using ((select private.is_mellanni_admin()));

create policy "Admin creates runs"
on public.runs for insert
to authenticated
with check ((select private.is_mellanni_admin()));

create policy "Admin updates runs"
on public.runs for update
to authenticated
using ((select private.is_mellanni_admin()))
with check ((select private.is_mellanni_admin()));

create policy "Admin deletes runs"
on public.runs for delete
to authenticated
using ((select private.is_mellanni_admin()));
