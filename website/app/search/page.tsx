import type { Metadata } from "next";
import { SearchExplorer } from "@/components/search-explorer";
import { getPublishedDigests } from "@/lib/supabase-public";

export const metadata: Metadata = {
  title: "Search",
  description: "Search weekly marketing intelligence digests by topic, finding, or source.",
};

export const dynamic = "force-dynamic";

type SearchPageProps = {
  searchParams: Promise<{ q?: string | string[] }>;
};

export default async function SearchPage({ searchParams }: SearchPageProps) {
  const [digests, { q }] = await Promise.all([getPublishedDigests(), searchParams]);
  const initialQuery = (Array.isArray(q) ? q[0] : q)?.slice(0, 200) ?? "";

  return (
    <div className="shell interior-page">
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">Research archive</p>
          <h1>Search every signal.</h1>
        </div>
        <p>
          Look across Actions, External Signals, topics, and named sources. Each result opens the exact finding.
        </p>
      </header>
      <SearchExplorer digests={digests} initialQuery={initialQuery} />
    </div>
  );
}
