import Link from "next/link";
import { DigestCard } from "@/components/digest-card";
import { getPublishedDigests } from "@/lib/supabase-public";

export const revalidate = 60;

export default async function HomePage() {
  const digests = await getPublishedDigests();
  const latestDigest = digests[0];

  return (
    <>
      <section className="shell home-hero" aria-labelledby="home-title">
        <div className="hero-copy">
          <p className="eyebrow">Weekly research bulletin</p>
          <h1 id="home-title">Marketing signals deserve context.</h1>
          <p className="hero-deck">
            Mellanni Marketing Intelligence brings sales economics, advertising, inventory, and search behavior into one readable weekly review.
          </p>
          <div className="hero-actions">
            {latestDigest ? (
              <Link className="primary-link" href={"/digests/" + latestDigest.slug}>
                Read latest digest <span aria-hidden="true">→</span>
              </Link>
            ) : null}
            <Link className="text-link" href="/search">Search the archive</Link>
          </div>
        </div>
        <aside className="editorial-note" aria-labelledby="editorial-note-title">
          <p className="issue-number">Editorial note / 01</p>
          <h2 id="editorial-note-title">Evidence before narrative</h2>
          <p>
            Each briefing is structured to separate observed signals, source context, and interpretation. The sample edition demonstrates that format without reporting account performance.
          </p>
        </aside>
      </section>

      <section className="feature-band">
        <div className="shell feature-grid">
          <div>
            <p className="eyebrow">Latest briefing</p>
            <h2>A single reading of the week, not four disconnected reports.</h2>
          </div>
          <p>
            The editorial sequence starts with business economics, then checks advertising, availability, and search behavior for explanations that hold together.
          </p>
        </div>
      </section>

      <section className="shell archive-section" id="archive" aria-labelledby="archive-title">
        <div className="section-heading">
          <div>
            <p className="eyebrow">The archive</p>
            <h2 id="archive-title">Weekly digests</h2>
          </div>
          <Link className="text-link" href="/calendar">View publication calendar</Link>
        </div>
        {digests.length ? (
          <div className="digest-list">
            {digests.map((digest) => <DigestCard key={digest.slug} digest={digest} />)}
          </div>
        ) : (
          <div className="empty-state">
            <p className="eyebrow">No published digest</p>
            <h3>The first briefing is being prepared.</h3>
            <p>Published editions will appear here without a website redeploy.</p>
          </div>
        )}
      </section>

      <section className="shell reading-guide" aria-labelledby="reading-guide-title">
        <div className="reading-guide-intro">
          <p className="eyebrow">Reading standard</p>
          <h2 id="reading-guide-title">What every digest preserves</h2>
        </div>
        <ol>
          <li>
            <span>01</span>
            <div>
              <h3>Source visibility</h3>
              <p>Primary references stay attached to the reasoning they support.</p>
            </div>
          </li>
          <li>
            <span>02</span>
            <div>
              <h3>Signal boundaries</h3>
              <p>Observed data, reporting timing, and interpretation remain distinct.</p>
            </div>
          </li>
          <li>
            <span>03</span>
            <div>
              <h3>Connected decisions</h3>
              <p>No isolated metric is asked to explain the full business picture.</p>
            </div>
          </li>
        </ol>
      </section>
    </>
  );
}
