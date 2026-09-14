-- The preceding restoration migration used legacy proof only to restore three
-- exact, previously approved digest bodies. Keep those audit rows, but do not
-- allow legacy proof to authorize any future draft-to-published transition.
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
      and manifest -> 'runProof' ->> 'schema_version' = '2'
      and manifest -> 'runProof' ->> 'agentic_verified' = 'true'
  );
$$;

revoke all on function private.has_verified_digest_publication_basis(uuid, text)
  from public, anon, authenticated;

do $$
declare
  published_count integer;
begin
  select count(*)
  into published_count
  from public.digests
  where slug in (
    '2026-08-27-growth-needs-proof',
    '2026-08-28-contribution-gates-and-funnel-economics',
    '2026-08-31-weekly-marketing-digest'
  )
    and status = 'published'
    and content_sha256 is not null;

  if published_count <> 3 then
    raise exception 'legacy publication lock expected 3 published rows, found %', published_count;
  end if;
end;
$$;
