import Link from "next/link";
import { DigestCard } from "@/components/digest-card";
import { digestFindings, digestHref, formatDigestDate } from "@/lib/digests";
import { getPublishedDigests } from "@/lib/supabase-public";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const digests = await getPublishedDigests();
  const [latest, ...archive] = digests;

  if (!latest) {
    return (
      <section className="shell interior-page" aria-labelledby="home-empty-title">
        <div className="empty-state">
          <p className="eyebrow">No published digest</p>
          <h1 id="home-empty-title" className="empty-title">The first briefing is being prepared.</h1>
          <p>Published editions appear here as soon as they are released; no redeploy is needed.</p>
        </div>
      </section>
    );
  }

  const findings = digestFindings(latest);
  const contradictions = findings.filter(({ item }) => item.memory.outcome === "contradicts");

  return (
    <>
      <section className="shell latest-digest" aria-labelledby="latest-title">
        <div className="latest-meta">
          <p className="eyebrow">Latest weekly digest</p>
          <time dateTime={latest.date}>{formatDigestDate(latest.date)}</time>
        </div>
        <h1 id="latest-title">
          <Link href={digestHref(latest.slug)}>{latest.title}</Link>
        </h1>
        <p className="latest-summary">{latest.summary}</p>

        {contradictions.length ? (
          <section className="contradiction-panel latest-contradictions" aria-labelledby="latest-contradictions-title">
            <p className="eyebrow">Contradictions first</p>
            <h2 id="latest-contradictions-title">This week conflicts with Professional Memory.</h2>
            <ul>
              {contradictions.map(({ item }) => (
                <li key={item.id}>
                  <Link href={digestHref(latest.slug, item.id)}>{item.title}</Link>
                  <p>{item.memory.decisionImpact}</p>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {findings.length ? (
          <ol className="latest-findings" aria-label="Items in the latest digest">
            {findings.map(({ kind, item }) => (
              <li key={item.id}>
                <span className="overview-kind">{kind === "action" ? "Action" : "Signal"}</span>
                <div>
                  <Link className="latest-finding-title" href={digestHref(latest.slug, item.id)}>{item.title}</Link>
                  <p>{kind === "action" ? item.guidance : item.whyItMatters}</p>
                </div>
              </li>
            ))}
          </ol>
        ) : null}

        <div className="hero-actions">
          <Link className="primary-link" href={digestHref(latest.slug)}>
            Read the full digest <span aria-hidden="true">→</span>
          </Link>
          <Link className="text-link" href="/search">Search the archive</Link>
        </div>
      </section>

      {archive.length ? (
        <section className="shell archive-section" id="archive" aria-labelledby="archive-title">
          <div className="section-heading">
            <div>
              <p className="eyebrow">The archive</p>
              <h2 id="archive-title">Earlier digests</h2>
            </div>
            <Link className="text-link" href="/calendar">Browse by month</Link>
          </div>
          <div className="digest-list">
            {archive.map((digest) => <DigestCard key={digest.slug} digest={digest} />)}
          </div>
        </section>
      ) : null}
    </>
  );
}
