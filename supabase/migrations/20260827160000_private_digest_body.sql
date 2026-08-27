alter table public.digests
  add column private_body jsonb not null default '{}'::jsonb
  check (jsonb_typeof(private_body) = 'object');

alter table public.runs
  add column outcome text not null default 'collection'
    check (outcome in ('collection', 'digest', 'no-digest')),
  add column outcome_reason text not null default '';

-- Public readers get only public digest columns. Authenticated admin retains
-- full-row access through the existing admin RLS policy.
revoke select on table public.digests from anon, authenticated;
grant select (
  id, slug, published_on, status, title, summary, body,
  published_at, created_at, updated_at
) on table public.digests to anon;
grant select on table public.digests to authenticated;

drop policy "Published digests are public" on public.digests;

create policy "Published digests are public"
on public.digests for select
to anon
using (status = 'published');
