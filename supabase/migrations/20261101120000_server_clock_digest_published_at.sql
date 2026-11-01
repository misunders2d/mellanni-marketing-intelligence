-- Publication time comes from the database clock on every path. The admin
-- console updates digests directly; the guard already enforces verified run
-- proof there, and now also owns published_at so a client cannot set it.
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
    new.published_at := timezone('utc', now());
  elsif new.status = 'published' then
    new.published_at := old.published_at;
  else
    new.published_at := null;
  end if;

  return new;
end;
$$;

revoke all on function private.guard_digest_content_and_publication()
  from public, anon, authenticated;
