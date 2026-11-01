import type { ReactNode } from "react";
import {
  digestFindings,
  formatDigestDate,
  isNotableMemory,
  type Digest,
  type DigestAction,
  type DigestMemory,
  type DigestSignal,
  type DigestSkillReference,
  type DigestSource,
} from "@/lib/digests";

function citedSources(ids: readonly string[], sources: readonly DigestSource[]) {
  return ids.flatMap((id) => {
    const source = sources.find((candidate) => candidate.id === id);
    return source ? [source] : [];
  });
}

function SourceLinks({ ids, sources }: { ids: readonly string[]; sources: readonly DigestSource[] }) {
  const selected = citedSources(ids, sources);
  if (!selected.length) return null;

  return (
    <p className="finding-sources">
      <span>Evidence</span>{" "}
      {selected.map((source, index) => (
        <span key={source.id}>
          {index ? ", " : ""}
          <a href={source.url} target="_blank" rel="noreferrer">
            {source.name}
            <span className="visually-hidden"> (opens in a new tab)</span>
            <span aria-hidden="true"> ↗</span>
          </a>
        </span>
      ))}
    </p>
  );
}

function MemoryNote({ memory }: { memory: DigestMemory }) {
  if (!isNotableMemory(memory)) return null;
  const label = memory.outcome === "contradicts" ? "Contradicts prior memory" : "Extends prior memory";
  return (
    <aside className={`memory-note memory-${memory.outcome}`}>
      <p className="evidence-label">{label}</p>
      <p>{memory.comparison}</p>
      <p><strong>Decision impact:</strong> {memory.decisionImpact}</p>
    </aside>
  );
}

function SkillReferences({ skills }: { skills: readonly DigestSkillReference[] }) {
  if (!skills.length) return null;
  return (
    <section className="skill-references" aria-label="Analyst playbooks">
      <p className="evidence-label">Analyst playbooks</p>
      <ul>
        {skills.map((skill) => (
          <li key={skill.uri}>
            <p>{skill.applicability}</p>
            <p><strong>Next:</strong> {skill.intendedNextOperation}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function FindingHeader({ index, kind, title }: { index: number; kind: string; title: string }) {
  return (
    <header className="finding-header">
      <span aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
      <div>
        <p className="finding-kind">{kind}</p>
        <h3>{title}</h3>
      </div>
    </header>
  );
}

function BackToOverview() {
  return (
    <p className="finding-back">
      <a href="#overview">Back to overview <span aria-hidden="true">↑</span></a>
    </p>
  );
}

function ActionItem({ action, index, sources }: { action: DigestAction; index: number; sources: readonly DigestSource[] }) {
  const evidence = action.mellanniEvidence;
  return (
    <article className="action-item" id={action.id}>
      <FindingHeader index={index} kind={`Action · ${action.confidence} confidence`} title={action.title} />
      <MemoryNote memory={action.memory} />
      <section className="guidance-block" aria-label="Recommended guidance">
        <p className="guidance-lead">{action.guidance}</p>
        <dl className="decision-grid">
          <div><dt>Timebox</dt><dd>{action.timebox}</dd></div>
          <div><dt>KPI</dt><dd>{action.kpi}</dd></div>
          <div><dt>Success</dt><dd>{action.successCondition}</dd></div>
          <div><dt>Stop</dt><dd>{action.stopCondition}</dd></div>
        </dl>
      </section>
      <section className="business-evidence" aria-label="Mellanni evidence basis">
        <p className="evidence-label">Mellanni evidence</p>
        <p>{evidence.conclusion}</p>
      </section>
      <p className="external-signal">{action.externalSignal}</p>
      <SourceLinks ids={action.sourceIds} sources={sources} />
      <details className="finding-details">
        <summary>Evidence scope, limits, and playbooks</summary>
        <dl className="evidence-scope">
          <div><dt>Scope</dt><dd>{evidence.entityScope}</dd></div>
          <div><dt>Source</dt><dd>{evidence.source}</dd></div>
          <div><dt>Window</dt><dd>{evidence.window}</dd></div>
          <div><dt>Grain</dt><dd>{evidence.grain}</dd></div>
        </dl>
        {action.limitations.length ? (
          <div className="limitations">
            <p className="evidence-label">Limits</p>
            <ul>{action.limitations.map((limit) => <li key={limit}>{limit}</li>)}</ul>
          </div>
        ) : null}
        <SkillReferences skills={action.skillReferences} />
      </details>
      <BackToOverview />
    </article>
  );
}

function SignalItem({ signal, index, sources }: { signal: DigestSignal; index: number; sources: readonly DigestSource[] }) {
  return (
    <article className="signal-item" id={signal.id}>
      <FindingHeader index={index} kind="External signal" title={signal.title} />
      <p className="external-signal">{signal.externalSignal}</p>
      <MemoryNote memory={signal.memory} />
      <div className="signal-decision">
        <p><strong>Why it matters:</strong> {signal.whyItMatters}</p>
        <p><strong>Next validation:</strong> {signal.nextValidation}</p>
      </div>
      <SourceLinks ids={signal.sourceIds} sources={sources} />
      {signal.skillReferences.length ? (
        <details className="finding-details">
          <summary>Analyst playbooks</summary>
          <SkillReferences skills={signal.skillReferences} />
        </details>
      ) : null}
      <BackToOverview />
    </article>
  );
}

function DigestOverview({ digest }: { digest: Digest }) {
  const findings = digestFindings(digest);
  if (!findings.length) return null;
  return (
    <nav className="digest-overview" id="overview" aria-labelledby="overview-title">
      <p className="eyebrow" id="overview-title">This edition · {findings.length} {findings.length === 1 ? "item" : "items"}</p>
      <ol>
        {findings.map(({ kind, item }) => (
          <li key={item.id} data-kind={kind}>
            <span className="overview-kind">{kind === "action" ? "Action" : "Signal"}</span>
            <a className="overview-title" href={`#${item.id}`}>{item.title}</a>
            <span className="overview-meta">
              {kind === "action"
                ? <>{item.kpi}<span aria-hidden="true"> · </span>{item.timebox}<span aria-hidden="true"> · </span>{item.confidence} confidence</>
                : item.nextValidation}
            </span>
            {item.memory.outcome === "contradicts" ? <span className="overview-flag">Contradicts memory</span> : null}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function DigestView({ digest, banner }: { digest: Digest; banner?: ReactNode }) {
  const structured = Boolean(digest.actions.length || digest.signals.length);
  const findings = digestFindings(digest);
  const contradictions = findings.filter(({ item }) => item.memory.outcome === "contradicts");
  // Short labels match the numbered finding headers; full titles stay in the overview.
  const citations = new Map<string, { id: string; label: string; title: string }[]>();
  const cite = (item: { id: string; title: string; sourceIds: readonly string[] }, label: string) => {
    for (const sourceId of item.sourceIds) {
      citations.set(sourceId, [...(citations.get(sourceId) ?? []), { id: item.id, label, title: item.title }]);
    }
  };
  digest.actions.forEach((action, index) => cite(action, `Action ${index + 1}`));
  digest.signals.forEach((signal, index) => cite(signal, `Signal ${index + 1}`));

  return (
    <>
      {banner}
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
            Every metric, identifier, and source in it is illustrative. It reports no real Mellanni results.
          </p>
        </aside>
      ) : null}

      {contradictions.length ? (
        <section className="contradiction-panel" aria-labelledby="contradictions-title">
          <p className="eyebrow">Contradictions first</p>
          <h2 id="contradictions-title">External evidence conflicts with Professional Memory.</h2>
          <ul>
            {contradictions.map(({ item }) => (
              <li key={item.id}>
                <a href={`#${item.id}`}>{item.title}</a>
                <p>{item.memory.comparison}</p>
                <p><strong>Current decision:</strong> {item.memory.decisionImpact}</p>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <DigestOverview digest={digest} />

      <div className="digest-layout">
        <div className="digest-content">
          {structured ? (
            <>
              <section className="actions" aria-labelledby="actions-title">
                <div className="section-heading compact-heading">
                  <div>
                    <p className="eyebrow">Backed by Mellanni data</p>
                    <h2 id="actions-title">Mellanni actions</h2>
                  </div>
                </div>
                {digest.actions.length ? (
                  <ol className="action-list">
                    {digest.actions.map((action, index) => (
                      <li key={action.id}>
                        <ActionItem action={action} index={index} sources={digest.sources} />
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="section-empty">No signal met the Mellanni-evidence bar for an Action this edition. Useful external knowledge remains below.</p>
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
                        <SignalItem signal={signal} index={index} sources={digest.sources} />
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
                  {source.name}
                  <span className="visually-hidden"> (opens in a new tab)</span>
                  <span aria-hidden="true"> ↗</span>
                </a>
                <p>{source.note}</p>
                {citations.get(source.id)?.length ? (
                  <p className="source-cited-in">
                    Cited in{" "}
                    {citations.get(source.id)?.map((finding, index) => (
                      <span key={finding.id}>
                        {index ? ", " : ""}
                        <a href={`#${finding.id}`} title={finding.title}>{finding.label}</a>
                      </span>
                    ))}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </>
  );
}
