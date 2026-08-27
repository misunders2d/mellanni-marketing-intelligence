import type { Metadata } from "next";
import { SearchExplorer } from "@/components/search-explorer";
import { getPublishedDigests } from "@/lib/supabase-public";

export const metadata: Metadata = {
  title: "Search",
  description: "Search weekly marketing intelligence digests by topic, finding, or source.",
};

export const revalidate = 60;

export default async function SearchPage() {
  const digests = await getPublishedDigests();

  return (
    <div className="shell interior-page">
      <header className="page-header split-header">
        <div>
          <p className="eyebrow">Research archive</p>
          <h1>Search every signal.</h1>
        </div>
        <p>
          Look across briefing titles, findings, topics, and named sources. Fuzzy matching helps when the exact wording is not at hand.
        </p>
      </header>
      <SearchExplorer digests={digests} />
    </div>
  );
}
