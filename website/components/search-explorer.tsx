"use client";

import { useMemo, useState } from "react";
import { DigestCard } from "@/components/digest-card";
import type { Digest } from "@/lib/digests";
import { indexDigest, searchDigestIndex } from "@/lib/search";

export function SearchExplorer({ digests }: { digests: readonly Digest[] }) {
  const [query, setQuery] = useState("");
  const searchIndex = useMemo(() => digests.map(indexDigest), [digests]);
  const results = useMemo(
    () => searchDigestIndex(searchIndex, query),
    [query, searchIndex],
  );
  const hasQuery = query.trim().length > 0;

  return (
    <section className="search-explorer" aria-labelledby="search-heading">
      <h2 id="search-heading" className="visually-hidden">
        Search the digest archive
      </h2>
      <div className="search-control">
        <label htmlFor="digest-search">Search by signal, topic, or source</label>
        <div className="search-input-row">
          <input
            id="digest-search"
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Try ‘inventry’, ‘profitability’, or ‘Amazon Ads’"
            autoComplete="off"
            spellCheck="false"
          />
          {hasQuery ? (
            <button type="button" className="secondary-button" onClick={() => setQuery("")}>
              Clear
            </button>
          ) : null}
        </div>
        <p className="search-help">
          Search includes digest titles, summaries, findings, topics, and source names. Close misspellings are welcome.
        </p>
      </div>

      {!hasQuery ? (
        <div className="search-prompt">
          <p className="eyebrow">Archive search</p>
          <h3>Start with the question you are investigating.</h3>
          <p>
            A topic such as inventory or a source such as Amazon Ads will surface every related weekly briefing.
          </p>
        </div>
      ) : results.length ? (
        <div className="search-results">
          <p className="result-count" role="status" aria-live="polite">
            {results.length} {results.length === 1 ? "digest" : "digests"} found
          </p>
          {results.map(({ digest }) => (
            <DigestCard key={digest.slug} digest={digest} />
          ))}
        </div>
      ) : (
        <div className="empty-state" role="status" aria-live="polite">
          <p className="eyebrow">No matching digest</p>
          <h3>Try a broader signal or source.</h3>
          <p>
            Check the spelling, remove one term, or search for profitability, advertising, inventory, or keywords.
          </p>
          <button type="button" className="secondary-button" onClick={() => setQuery("")}>
            Reset search
          </button>
        </div>
      )}
    </section>
  );
}
