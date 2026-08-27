create schema if not exists private;

revoke all on schema private from public;
grant usage on schema private to authenticated;

create or replace function private.is_mellanni_admin()
returns boolean
language sql
stable
security invoker
set search_path = ''
as $$
  select lower(coalesce(auth.jwt() ->> 'email', '')) = 'sergey@mellanni.com';
$$;

revoke all on function private.is_mellanni_admin() from public;
grant execute on function private.is_mellanni_admin() to authenticated;

create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table public.sources (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  name text not null,
  home_url text not null check (home_url ~ '^https?://'),
  priority text not null default 'A',
  why text not null default '',
  include_patterns text[] not null default '{}',
  allowed_hosts text[] not null default '{}',
  feed_urls text[] not null default '{}',
  max_items integer not null default 5 check (max_items between 1 and 100),
  max_feed_candidates integer not null default 8 check (max_feed_candidates between 1 and 100),
  enabled boolean not null default true,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create index sources_enabled_name_idx on public.sources (enabled, name);

create trigger sources_set_updated_at
before update on public.sources
for each row execute function public.set_updated_at();

create table public.digests (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique check (slug ~ '^[a-z0-9]+(?:-[a-z0-9]+)*$'),
  published_on date not null,
  status text not null default 'draft' check (status in ('draft', 'published')),
  title text not null,
  summary text not null,
  body jsonb not null check (jsonb_typeof(body) = 'object'),
  published_at timestamptz,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now()),
  check (status = 'draft' or published_at is not null)
);

create index digests_publication_idx on public.digests (status, published_on desc);

create trigger digests_set_updated_at
before update on public.digests
for each row execute function public.set_updated_at();

create table public.runs (
  id uuid primary key default gen_random_uuid(),
  status text not null check (status in ('running', 'succeeded', 'failed')),
  started_at timestamptz not null default timezone('utc', now()),
  finished_at timestamptz,
  source_count integer not null default 0 check (source_count >= 0),
  item_count integer not null default 0 check (item_count >= 0),
  warning_count integer not null default 0 check (warning_count >= 0),
  error_count integer not null default 0 check (error_count >= 0),
  manifest jsonb not null default '{}'::jsonb check (jsonb_typeof(manifest) = 'object'),
  digest_id uuid references public.digests(id) on delete set null,
  created_at timestamptz not null default timezone('utc', now())
);

create index runs_started_at_idx on public.runs (started_at desc);

alter table public.sources enable row level security;
alter table public.digests enable row level security;
alter table public.runs enable row level security;

revoke all on table public.sources from anon, authenticated;
revoke all on table public.digests from anon, authenticated;
revoke all on table public.runs from anon, authenticated;

grant select, insert, update, delete on table public.sources to authenticated;
grant select on table public.digests to anon, authenticated;
grant insert, update, delete on table public.digests to authenticated;
grant select, insert, update, delete on table public.runs to authenticated;

create policy "Published digests are public"
on public.digests for select
to anon, authenticated
using (status = 'published');

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

insert into public.sources (
  slug, name, home_url, priority, why, include_patterns, allowed_hosts,
  feed_urls, max_items, max_feed_candidates, enabled
)
values
  ('marketplace-pulse', 'Marketplace Pulse', 'https://www.marketplacepulse.com/', 'A', 'Independent, data-driven Amazon and marketplace structural changes.', array['/articles/', '/news/'], '{}', '{}', 5, 8, true),
  ('practical-ecommerce', 'Practical Ecommerce', 'https://www.practicalecommerce.com/', 'A', 'Practical ecommerce, paid media, CRO, analytics, AI, and operator tactics.', '{}', '{}', '{}', 5, 8, true),
  ('dtc-newsletter', 'DTC Newsletter', 'https://www.directtoconsumer.co/newsletters', 'A', 'Tactical DTC creative, attribution, lifecycle, landing-page, and channel experiments.', array['/newsletter', '/blogs/'], '{}', '{}', 5, 8, true),
  ('nik-sharma', 'Nik Sharma Newsletter', 'https://subscribe.nik.co/', 'A', 'Active operator lessons on offers, conversion, creative, launches, and channel mix.', '{}', array['.nik.co'], '{}', 5, 8, true),
  ('sell-on-amazon', 'Sell on Amazon Announcements', 'https://sell.amazon.com/blog/announcements', 'A', 'First-party Seller Central, FBA, product, and policy announcements.', array['/blog/'], '{}', '{}', 5, 8, true),
  ('amazon-ads-news', 'Amazon Ads What''s New', 'https://advertising.amazon.com/library/newsroom', 'A', 'First-party Amazon Ads, DSP, AMC, targeting, creative, and measurement updates.', array['/library/news/'], '{}', '{}', 5, 8, true),
  ('marketing-operators', 'Marketing Operators', 'https://www.9operators.com/podcast/marketing-operators', 'A', 'Hands-on ecommerce growth and experimentation by active operators.', array['/episodes/'], array['portal.9operators.com'], '{}', 5, 8, true),
  ('nine-operators', '9 Operators', 'https://www.9operators.com/podcast/nine-operators', 'A', 'Scaling, category expansion, org design, and operating decisions from ecommerce leaders.', array['/episodes/'], array['portal.9operators.com'], '{}', 5, 8, true),
  ('limited-supply', 'Limited Supply', 'https://visit.nik.co/limited-supply/', 'A', 'DTC founder and operator discussion on offers, economics, creative, and brand strategy.', array['limited-supply'], '{}', array['https://feeds.megaphone.fm/limited-supply'], 5, 8, true),
  ('ppc-den', 'The PPC Den', 'https://www.adbadger.com/category/podcast/', 'A', 'Executable Amazon PPC structures, measurement, and optimization tactics.', array['/podcast/'], '{}', array['https://www.adbadger.com/category/podcast/feed/'], 5, 8, true),
  ('seller-sessions', 'Seller Sessions', 'https://sellersessions.com/podcast/', 'A', 'Experimental Amazon conversion, ranking, listing, data, and AI workflows.', array['/podcast/'], array['sellersessions.libsyn.com'], array['https://sellersessions.libsyn.com/rss'], 5, 8, true),
  ('smartest-amazon-seller', 'The Smartest Amazon Seller', 'https://scottneedham.podbean.com/', 'A', 'Amazon operator and data perspective on category strategy and marketplace economics.', array['/e/'], '{}', '{}', 5, 8, true)
on conflict (slug) do nothing;

insert into public.digests (
  slug, published_on, status, title, summary, body, published_at
)
values (
  'sample-weekly-intelligence-brief',
  '2026-08-24',
  'published',
  'One weekly review, four connected lenses',
  'A sample edition showing how sales economics, advertising, inventory, and search behavior can be read together without turning an early signal into a claim.',
  jsonb_build_object(
    'topics', array['Profitability', 'Amazon Ads', 'Inventory', 'Keyword intelligence'],
    'findings', array[
      'Begin with sales economics: review gross and net sales, fees, promotions, and product-level contribution together before interpreting top-line movement.',
      'Read advertising in context: use first-party Amazon Ads reporting, separate delivery from attributed outcomes, and account for reporting windows before drawing a conclusion.',
      'Check inventory before diagnosing demand: stock availability and stockout risk can change what conversion and sales patterns appear to mean.',
      'Reconcile keyword discovery with Search Query Performance behavior so reach, clicks, and purchase intent remain distinct signals.'
    ],
    'sources', jsonb_build_array(
      jsonb_build_object('name', 'Amazon Ads reporting documentation', 'url', 'https://advertising.amazon.com/API/docs/en-us/guides/reporting/v3/overview', 'note', 'First-party reporting concepts and report workflow reference.'),
      jsonb_build_object('name', 'Selling Partner API Reports reference', 'url', 'https://developer-docs.amazon.com/sp-api/docs/reports-api-v2021-06-30-reference', 'note', 'Official report retrieval and report type reference.'),
      jsonb_build_object('name', 'Amazon Search Query Performance dashboard', 'url', 'https://sellercentral.amazon.com/search-query-performance/dashboard', 'note', 'Seller Central source for search funnel behavior.')
    ),
    'isSample', true
  ),
  timezone('utc', now())
)
on conflict (slug) do nothing;
