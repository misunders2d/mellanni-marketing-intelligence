import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  formatDigestDate,
  type DigestMemory,
  type DigestSkillReference,
  type DigestSource,
} from "@/lib/digests";
import { getPublishedDigestBySlug } from "@/lib/supabase-public";

type DigestPageProps = {
  params: Promise<{ slug: string }>;
};

export const revalidate = 60;

function SourceLinks({ ids, sources }: { ids: readonly string[]; sources: readonly DigestSource[] }) {
  const selected = ids.flatMap((id) => {
    const source = sources.find((candidate) => candidate.id === id);
    return source ? [source] : [];
  });
  if (!selected.length) return null;

  return (
    <p className="finding-sources">
      <span>Evidence</span>{" "}
      {selected.map((source, index) => (
        <span key={source.id}>
          {index ? ", " : ""}
          <a href={`#source-${source.id}`}>{source.name}</a>
        </span>
      ))}
    </p>
  );
}

function MemoryNote({ memory }: { memory: DigestMemory }) {
  const label = memory.outcome.replaceAll("-", " ");
  return (
    <aside className={`memory-note memory-${memory.outcome}`}>
      <p className="evidence-label">Professional Memory · {label}</p>
      <p>{memory.comparison}</p>
      <p><strong>Decision impact:</strong> {memory.decisionImpact}</p>
    </aside>
  );
}

function SkillReferences({ skills }: { skills: readonly DigestSkillReference[] }) {
  if (!skills.length) return null;
  return (
    <section className="skill-references" aria-label="Applicable Mellanni playbooks">
      <p className="evidence-label">Applicable playbooks</p>
      <ul>
        {skills.map((skill) => (
          <li key={skill.uri}>
            <code>{skill.uri}</code>
            <p>{skill.applicability}</p>
            <p><strong>Needs:</strong> {skill.requiredInputs.join(", ")}</p>
            <p><strong>Next:</strong> {skill.intendedNextOperation}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

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

  const structured = Boolean(digest.actions.length || digest.signals.length);
  const contradictions = [
    ...digest.actions.map((item) => ({ id: item.id, title: item.title, memory: item.memory })),
    ...digest.signals.map((item) => ({ id: item.id, title: item.title, memory: item.memory })),
  ].filter((item) => item.memory.outcome === "contradicts");

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

      {contradictions.length ? (
        <section className="contradiction-panel" aria-labelledby="contradictions-title">
          <p className="eyebrow">Contradictions first</p>
          <h2 id="contradictions-title">External evidence conflicts with Professional Memory.</h2>
          <ul>
            {contradictions.map((item) => (
              <li key={item.id}>
                <a href={`#${item.id}`}>{item.title}</a>
                <p>{item.memory.comparison}</p>
                <p><strong>Current decision:</strong> {item.memory.decisionImpact}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <div className="digest-layout">
        <div className="digest-content">
          {structured ? (
            <>
              <section className="actions" aria-labelledby="actions-title">
                <div className="section-heading compact-heading">
                  <div>
                    <p className="eyebrow">Backed by private Mellanni evidence</p>
                    <h2 id="actions-title">Mellanni actions</h2>
                  </div>
                </div>
                {digest.actions.length ? (
                  <ol className="action-list">
                    {digest.actions.map((action, index) => (
                      <li key={action.id}>
                        <article className="action-item" id={action.id}>
                          <header className="finding-header">
                            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                            <div>
                              <p className="finding-kind">Action · {action.confidence} confidence</p>
                              <h3>{action.title}</h3>
                            </div>
                          </header>
                          <p className="external-signal">{action.externalSignal}</p>
                          <SourceLinks ids={action.sourceIds} sources={digest.sources} />
                          <MemoryNote memory={action.memory} />

                          <section className="business-evidence" aria-label="Mellanni evidence basis">
                            <p className="evidence-label">Private Mellanni evidence · values withheld</p>
                            <p>{action.mellanniEvidence.conclusion}</p>
                            <dl>
                              <div><dt>Scope</dt><dd>{action.mellanniEvidence.entityScope}</dd></div>
                              <div><dt>Source</dt><dd>{action.mellanniEvidence.source}</dd></div>
                              <div><dt>Window</dt><dd>{action.mellanniEvidence.window}</dd></div>
                              <div><dt>Grain</dt><dd>{action.mellanniEvidence.grain}</dd></div>
                            </dl>
                          </section>

                          <section className="guidance-block" aria-label="Recommended guidance">
                            <p className="evidence-label">Guidance</p>
                            <p>{action.guidance}</p>
                            <dl className="decision-grid">
                              <div><dt>Timebox</dt><dd>{action.timebox}</dd></div>
                              <div><dt>KPI</dt><dd>{action.kpi}</dd></div>
                              <div><dt>Success</dt><dd>{action.successCondition}</dd></div>
                              <div><dt>Stop</dt><dd>{action.stopCondition}</dd></div>
                            </dl>
                          </section>

                          <div className="limitations">
                            <p className="evidence-label">Limits</p>
                            <ul>{action.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
                          </div>
                          <SkillReferences skills={action.skillReferences} />
                        </article>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="section-empty">No signal met the private-evidence bar for an Action this edition. Useful external knowledge remains below.</p>
                )}
              </section>

              {digest.signals.length ? (
                <section className="external-signals" aria-labelledby="signals-title">
                  <div className="section-heading compact-heading">
                    <div>
                      <p className="eyebrow">Broader ecommerce intelligence</p>
                      <h2 id="signals-title">External signals</h2>
                    </div>
                  </div>
                  <ol className="signal-list">
                    {digest.signals.map((signal, index) => (
                      <li key={signal.id}>
                        <article className="signal-item" id={signal.id}>
                          <header className="finding-header">
                            <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
                            <div>
                              <p className="finding-kind">External signal</p>
                              <h3>{signal.title}</h3>
                            </div>
                          </header>
                          <p className="external-signal">{signal.externalSignal}</p>
                          <SourceLinks ids={signal.sourceIds} sources={digest.sources} />
                          <MemoryNote memory={signal.memory} />
                          <div className="signal-decision">
                            <p><strong>Why it matters:</strong> {signal.whyItMatters}</p>
                            <p><strong>Next validation:</strong> {signal.nextValidation}</p>
                          </div>
                          <SkillReferences skills={signal.skillReferences} />
                        </article>
                      </li>
                    ))}
                  </ol>
                </section>
              ) : null}
            </>
          ) : (
            <section className="findings" aria-labelledby="findings-title">
              <div className="section-heading compact-heading">
                <div>
                  <p className="eyebrow">Legacy edition</p>
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
          )}
        </div>

        <aside className="source-notes" aria-labelledby="sources-title">
          <p className="eyebrow">Primary references</p>
          <h2 id="sources-title">Source notes</h2>
          <ul>
            {digest.sources.map((source) => (
              <li id={`source-${source.id}`} key={source.id}>
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
