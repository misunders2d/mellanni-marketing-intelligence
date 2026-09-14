create or replace function private.has_verified_digest_publication_basis(
  p_digest_id uuid,
  p_content_sha256 text
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
    from public.runs
    where digest_id = p_digest_id
      and status = 'succeeded'
      and outcome = 'digest'
      and manifest -> 'runProof' ->> 'digest_content_sha256'
          = p_content_sha256
      and (
        (
          manifest -> 'runProof' ->> 'schema_version' = '2'
          and manifest -> 'runProof' ->> 'agentic_verified' = 'true'
        )
        or (
          manifest -> 'runProof' ->> 'schema_version' = 'legacy-1'
          and manifest -> 'runProof' ->> 'legacy_approved_publication' = 'true'
        )
      )
  );
$$;

revoke all on function private.has_verified_digest_publication_basis(uuid, text)
  from public, anon, authenticated;

create or replace function private.guard_digest_content_and_publication()
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
    if new.content_sha256 is null or not private.has_verified_digest_publication_basis(
      old.id,
      new.content_sha256
    ) then
      raise exception 'digest % has no verified run for current content', new.slug;
    end if;
  end if;

  return new;
end;
$$;

revoke all on function private.guard_digest_content_and_publication()
  from public, anon, authenticated;

create or replace function public.publish_digest_with_verified_run(p_slug text)
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

  if saved_digest.content_sha256 is null or not private.has_verified_digest_publication_basis(
    saved_digest.id,
    saved_digest.content_sha256
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

with approved(slug, content_sha256, expected_updated_at) as (
  values
    (
      '2026-08-27-growth-needs-proof',
      'a48534d80e07a8d34dc3272b35cd6e81d5439bdfb5628b5953d8d2d8fde6b84c',
      '2026-09-08T16:57:36.699254+00:00'::timestamptz
    ),
    (
      '2026-08-28-contribution-gates-and-funnel-economics',
      '6b73e526fc8716009ae3c5fa60e85d5f4c80866731f4ad2f4685d1379304c2b0',
      '2026-09-08T16:57:36.699254+00:00'::timestamptz
    ),
    (
      '2026-08-31-weekly-marketing-digest',
      '0813c2093849104b82115c0f19b351e4315569eeab61dde726acb188de364cd3',
      '2026-09-08T16:57:36.699254+00:00'::timestamptz
    )
)
update public.digests as digest
set content_sha256 = approved.content_sha256
from approved
where digest.slug = approved.slug
  and digest.status = 'draft'
  and digest.content_sha256 is null
  and digest.updated_at = approved.expected_updated_at;

with approved(slug, content_sha256) as (
  values
    (
      '2026-08-27-growth-needs-proof',
      'a48534d80e07a8d34dc3272b35cd6e81d5439bdfb5628b5953d8d2d8fde6b84c'
    ),
    (
      '2026-08-28-contribution-gates-and-funnel-economics',
      '6b73e526fc8716009ae3c5fa60e85d5f4c80866731f4ad2f4685d1379304c2b0'
    ),
    (
      '2026-08-31-weekly-marketing-digest',
      '0813c2093849104b82115c0f19b351e4315569eeab61dde726acb188de364cd3'
    )
)
insert into public.runs (
  status,
  finished_at,
  source_count,
  item_count,
  warning_count,
  error_count,
  manifest,
  digest_id,
  outcome,
  outcome_reason,
  run_key
)
select
  'succeeded',
  timezone('utc', now()),
  0,
  0,
  0,
  0,
  jsonb_build_object(
    'runProof',
    jsonb_build_object(
      'schema_version', 'legacy-1',
      'digest_content_sha256', approved.content_sha256,
      'legacy_approved_publication', true,
      'reason', 'Restored exact previously approved content after proof migration'
    )
  ),
  digest.id,
  'digest',
  'One-time restoration of exact content approved before run-proof schema 2',
  'legacy-restore:' || approved.content_sha256
from approved
join public.digests as digest
  on digest.slug = approved.slug
 and digest.status = 'draft'
 and digest.content_sha256 = approved.content_sha256
on conflict (run_key) do nothing;

with approved(slug, content_sha256) as (
  values
    (
      '2026-08-27-growth-needs-proof',
      'a48534d80e07a8d34dc3272b35cd6e81d5439bdfb5628b5953d8d2d8fde6b84c'
    ),
    (
      '2026-08-28-contribution-gates-and-funnel-economics',
      '6b73e526fc8716009ae3c5fa60e85d5f4c80866731f4ad2f4685d1379304c2b0'
    ),
    (
      '2026-08-31-weekly-marketing-digest',
      '0813c2093849104b82115c0f19b351e4315569eeab61dde726acb188de364cd3'
    )
)
update public.digests as digest
set
  status = 'published',
  published_at = timezone('utc', now())
from approved
where digest.slug = approved.slug
  and digest.status = 'draft'
  and digest.content_sha256 = approved.content_sha256
  and private.has_verified_digest_publication_basis(
    digest.id,
    approved.content_sha256
  );

do $$
declare
  restored_count integer;
begin
  select count(*)
  into restored_count
  from public.digests
  where slug in (
    '2026-08-27-growth-needs-proof',
    '2026-08-28-contribution-gates-and-funnel-economics',
    '2026-08-31-weekly-marketing-digest'
  )
    and status = 'published'
    and content_sha256 is not null;

  if restored_count <> 3 then
    raise exception 'legacy digest restoration expected 3 rows, restored %', restored_count;
  end if;
end;
$$;
