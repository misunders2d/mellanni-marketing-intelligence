import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { formatDigestDate } from "@/lib/digests";
import { getPublishedDigestBySlug } from "@/lib/supabase-public";

type DigestPageProps = {
  params: Promise<{ slug: string }>;
};

export const revalidate = 60;

export async function generateMetadata({ params }: DigestPageProps): Promise<Metadata> {
  const { slug } = await params;
  const digest = await getPublishedDigestBySlug(slug);

  if (!digest) return { title: "Digest not found" };

  return {
    title: digest.title,
    description: digest.summary,
    openGraph: {
      title: digest.title,
      description: digest.summary,
      type: "article",
      publishedTime: digest.date,
    },
  };
}

export default async function DigestPage({ params }: DigestPageProps) {
  const { slug } = await params;
  const digest = await getPublishedDigestBySlug(slug);

  if (!digest) notFound();

  return (
    <article className="shell digest-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span aria-hidden="true">/</span>
        <span>Weekly digest</span>
      </nav>

      <header className="digest-header">
        <div className="digest-header-meta">
          <p className="eyebrow">Weekly intelligence digest</p>
          <time dateTime={digest.date}>{formatDigestDate(digest.date)}</time>
        </div>
        <h1>{digest.title}</h1>
        <p className="digest-summary">{digest.summary}</p>
        <ul className="topic-list" aria-label="Topics covered">
          {digest.topics.map((topic) => (
            <li key={topic}>{topic}</li>
          ))}
        </ul>
      </header>

      {digest.isSample ? (
        <aside className="sample-notice" aria-labelledby="sample-notice-title">
          <p className="eyebrow">Clearly labeled sample</p>
          <h2 id="sample-notice-title">This edition demonstrates the editorial format.</h2>
          <p>
            It uses known review themes only. It contains no account results, performance metrics, forecasts, or measured business claims.
          </p>
        </aside>
      ) : null}

      <div className="digest-layout">
        <section className="findings" aria-labelledby="findings-title">
          <div className="section-heading compact-heading">
            <div>
              <p className="eyebrow">The weekly reading</p>
              <h2 id="findings-title">Findings in context</h2>
            </div>
          </div>
          <ol>
            {digest.findings.map((finding, index) => (
              <li key={finding}>
                <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                <p>{finding}</p>
              </li>
            ))}
          </ol>
        </section>

        <aside className="source-notes" aria-labelledby="sources-title">
          <p className="eyebrow">Primary references</p>
          <h2 id="sources-title">Source notes</h2>
          <ul>
            {digest.sources.map((source) => (
              <li key={source.url}>
                <a href={source.url} target="_blank" rel="noreferrer">
                  {source.name} <span aria-hidden="true">↗</span>
                </a>
                <p>{source.note}</p>
              </li>
            ))}
          </ul>
        </aside>
      </div>

      <footer className="digest-footer">
        <p>Continue through the archive by signal or publication date.</p>
        <div>
          <Link className="primary-link" href="/search">Search digests</Link>
          <Link className="text-link" href="/calendar">Open calendar</Link>
        </div>
      </footer>
    </article>
  );
}
