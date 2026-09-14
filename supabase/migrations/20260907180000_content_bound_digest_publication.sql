alter table public.digests
  add column content_sha256 text
  check (content_sha256 is null or content_sha256 ~ '^[0-9a-f]{64}$');

alter table public.runs
  add column run_key text unique;

-- Existing publications predate content-bound proof. Fail closed until each is
-- regenerated as a verified draft and explicitly republished.
update public.digests
set status = 'draft', published_at = null
where status = 'published';

grant insert on table public.runs to service_role;

create function private.guard_digest_content_and_publication()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  content_changed boolean;
begin
  if tg_op = 'INSERT' then
    if new.status <> 'draft' or new.published_at is not null then
      raise exception 'new digest must start as draft';
    end if;
    return new;
  end if;

  content_changed :=
    new.slug is distinct from old.slug
    or new.published_on is distinct from old.published_on
    or new.title is distinct from old.title
    or new.summary is distinct from old.summary
    or new.body is distinct from old.body;

  if content_changed then
    new.status := 'draft';
    new.published_at := null;
    if new.content_sha256 is not distinct from old.content_sha256 then
      new.content_sha256 := null;
    end if;
  elsif new.content_sha256 is distinct from old.content_sha256 then
    new.status := 'draft';
    new.published_at := null;
  end if;

  if new.status = 'published' and old.status is distinct from 'published' then
    if new.content_sha256 is null or not exists (
      select 1
      from public.runs
      where digest_id = old.id
        and status = 'succeeded'
        and outcome = 'digest'
        and manifest -> 'runProof' ->> 'digest_content_sha256'
            = new.content_sha256
        and manifest -> 'runProof' ->> 'schema_version' = '2'
        and manifest -> 'runProof' ->> 'agentic_verified' = 'true'
    ) then
      raise exception 'digest % has no verified run for current content', new.slug;
    end if;
  end if;

  return new;
end;
$$;

revoke all on function private.guard_digest_content_and_publication()
  from public, anon, authenticated;

create trigger digests_guard_content_and_publication
before insert or update on public.digests
for each row execute function private.guard_digest_content_and_publication();

create function private.invalidate_digest_for_private_body_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  update public.digests
  set
    status = 'draft',
    published_at = null,
    content_sha256 = null
  where id = coalesce(new.digest_id, old.digest_id);
  return coalesce(new, old);
end;
$$;

revoke all on function private.invalidate_digest_for_private_body_change()
  from public, anon, authenticated;

create trigger digest_private_bodies_invalidate_digest
before insert or update or delete on public.digest_private_bodies
for each row execute function private.invalidate_digest_for_private_body_change();

drop function if exists public.upsert_digest_with_private_body(
  text, date, text, text, text, jsonb, jsonb, timestamptz
);

create function public.upsert_digest_with_private_body(
  p_slug text,
  p_published_on date,
  p_status text,
  p_title text,
  p_summary text,
  p_body jsonb,
  p_private_body jsonb,
  p_published_at timestamptz,
  p_content_sha256 text
)
returns setof public.digests
language plpgsql
security definer
set search_path = ''
as $$
declare
  saved_digest public.digests;
begin
  if p_status <> 'draft' then
    raise exception 'digest upsert must write draft status';
  end if;
  if p_published_at is not null then
    raise exception 'digest draft upsert cannot set published_at';
  end if;
  if p_content_sha256 is null or p_content_sha256 !~ '^[0-9a-f]{64}$' then
    raise exception 'invalid digest content hash';
  end if;

  insert into public.digests (
    slug, published_on, status, title, summary, body, published_at, content_sha256
  )
  values (
    p_slug, p_published_on, 'draft', p_title, p_summary, p_body, null, null
  )
  on conflict (slug) do update
  set
    published_on = excluded.published_on,
    status = 'draft',
    title = excluded.title,
    summary = excluded.summary,
    body = excluded.body,
    published_at = null,
    content_sha256 = null
  returning * into saved_digest;

  insert into public.digest_private_bodies (digest_id, private_body)
  values (saved_digest.id, p_private_body)
  on conflict (digest_id) do update
  set private_body = excluded.private_body;

  update public.digests
  set content_sha256 = p_content_sha256
  where id = saved_digest.id
  returning * into saved_digest;

  return next saved_digest;
end;
$$;

revoke all on function public.upsert_digest_with_private_body(
  text, date, text, text, text, jsonb, jsonb, timestamptz, text
) from public, anon, authenticated;
grant execute on function public.upsert_digest_with_private_body(
  text, date, text, text, text, jsonb, jsonb, timestamptz, text
) to service_role;

create function public.publish_digest_with_verified_run(p_slug text)
returns setof public.digests
language plpgsql
security definer
set search_path = ''
as $$
declare
  saved_digest public.digests;
begin
  select *
  into saved_digest
  from public.digests
  where slug = p_slug
  for update;

  if not found then
    raise exception 'digest % was not found', p_slug;
  end if;

  if saved_digest.content_sha256 is null or not exists (
    select 1
    from public.runs
    where digest_id = saved_digest.id
      and status = 'succeeded'
      and outcome = 'digest'
      and manifest -> 'runProof' ->> 'digest_content_sha256'
          = saved_digest.content_sha256
      and manifest -> 'runProof' ->> 'schema_version' = '2'
      and manifest -> 'runProof' ->> 'agentic_verified' = 'true'
  ) then
    raise exception 'digest % has no verified run for current content', p_slug;
  end if;

  update public.digests
  set
    status = 'published',
    published_at = timezone('utc', now())
  where id = saved_digest.id
  returning * into saved_digest;

  return next saved_digest;
end;
$$;

revoke all on function public.publish_digest_with_verified_run(text)
  from public, anon, authenticated;
grant execute on function public.publish_digest_with_verified_run(text)
  to service_role;
