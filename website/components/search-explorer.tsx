"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { formatDigestDate, type Digest } from "@/lib/digests";
import { indexDigests, searchIndex } from "@/lib/search";

const KIND_LABEL = { digest: "Digest", action: "Action", signal: "Signal" } as const;

export function SearchExplorer({ digests, initialQuery }: { digests: readonly Digest[]; initialQuery: string }) {
  const [query, setQuery] = useState(initialQuery);
  const index = useMemo(() => indexDigests(digests), [digests]);
  const results = useMemo(() => searchIndex(index, query), [index, query]);
  const hasQuery = query.trim().length > 0;

  // Keep the query in the address so a search can be shared or revisited.
  useEffect(() => {
    const url = new URL(window.location.href);
    if (query.trim()) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    window.history.replaceState(null, "", url);
  }, [query]);

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
          Results link straight to the matching Action or External Signal. Close misspellings are welcome.
        </p>
      </div>

      {!hasQuery ? (
        <div className="search-prompt">
          <p className="eyebrow">Archive search</p>
          <h3>Start with the question you are investigating.</h3>
          <p>
            A topic such as inventory or a source such as Amazon Ads surfaces every related finding across weekly briefings.
          </p>
        </div>
      ) : results.length ? (
        <div className="search-results">
          <p className="result-count" role="status" aria-live="polite">
            {results.length} {results.length === 1 ? "match" : "matches"}
          </p>
          <ol className="search-hit-list">
            {results.map((hit) => (
              <li className="search-hit" key={hit.key}>
                <p className="search-hit-meta">
                  <span className="overview-kind">{KIND_LABEL[hit.kind]}</span>
                  <span>{formatDigestDate(hit.digest.date)}</span>
                  {hit.kind !== "digest" ? <span className="search-hit-digest">{hit.digest.title}</span> : null}
                </p>
                <h3><Link href={hit.href}>{hit.title}</Link></h3>
                <p>{hit.snippet}</p>
              </li>
            ))}
          </ol>
        </div>
      ) : (
        <div className="empty-state" role="status" aria-live="polite">
          <p className="eyebrow">No matching finding</p>
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
