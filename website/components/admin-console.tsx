"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import Link from "next/link";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "@/lib/supabase-browser";

type SourceRow = {
  id: string;
  slug: string;
  name: string;
  home_url: string;
  priority: string;
  why: string;
  include_patterns: string[];
  allowed_hosts: string[];
  feed_urls: string[];
  max_items: number;
  max_feed_candidates: number;
  enabled: boolean;
};

type DigestAdminRow = {
  id: string;
  slug: string;
  title: string;
  published_on: string;
  status: "draft" | "published";
  private_body: {
    actions?: PrivateDecisionAction[];
  } | null;
};

type DigestPrivateBodyRow = {
  digest_id: string;
  private_body: DigestAdminRow["private_body"];
};

type PrivateDecisionAction = {
  id: string;
  title: string;
  privateDecision: {
    entityIds: string[];
    baseline: string;
    guidance: string;
    kpi: string;
    successCondition: string;
    stopCondition: string;
  };
};

type SourceDraft = {
  id?: string;
  slug: string;
  name: string;
  homeUrl: string;
  priority: string;
  why: string;
  includePatterns: string;
  allowedHosts: string;
  feedUrls: string;
  maxItems: string;
  maxFeedCandidates: string;
};

const EMPTY_SOURCE: SourceDraft = {
  slug: "",
  name: "",
  homeUrl: "",
  priority: "A",
  why: "",
  includePatterns: "",
  allowedHosts: "",
  feedUrls: "",
  maxItems: "5",
  maxFeedCandidates: "8",
};

function lines(value: string) {
  return value
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function slugFromName(value: string) {
  return value
    .trim()
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function sourceDraft(source: SourceRow): SourceDraft {
  return {
    id: source.id,
    slug: source.slug,
    name: source.name,
    homeUrl: source.home_url,
    priority: source.priority,
    why: source.why,
    includePatterns: source.include_patterns.join("\n"),
    allowedHosts: source.allowed_hosts.join("\n"),
    feedUrls: source.feed_urls.join("\n"),
    maxItems: String(source.max_items),
    maxFeedCandidates: String(source.max_feed_candidates),
  };
}

export function AdminConsole() {
  const supabase = getBrowserSupabase();
  const [session, setSession] = useState<Session | null>(null);
  const [authReady, setAuthReady] = useState(!supabase);
  const [sources, setSources] = useState<SourceRow[]>([]);
  const [digests, setDigests] = useState<DigestAdminRow[]>([]);
  const [draft, setDraft] = useState<SourceDraft>(EMPTY_SOURCE);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    if (!supabase) return;
    setBusy(true);
    setError("");

    const [sourceResult, digestResult, privateBodyResult] = await Promise.all([
      supabase.from("sources").select("*").order("name"),
      supabase
        .from("digests")
        .select("id,slug,title,published_on,status")
        .order("published_on", { ascending: false }),
      supabase
        .from("digest_private_bodies")
        .select("digest_id,private_body"),
    ]);

    if (sourceResult.error || digestResult.error || privateBodyResult.error) {
      setError(
        sourceResult.error?.message
          ?? digestResult.error?.message
          ?? privateBodyResult.error?.message
          ?? "Unable to load admin data.",
      );
    } else {
      const privateBodies = new Map(
        ((privateBodyResult.data ?? []) as DigestPrivateBodyRow[])
          .map((row) => [row.digest_id, row.private_body]),
      );
      setSources((sourceResult.data ?? []) as SourceRow[]);
      setDigests(
        (digestResult.data ?? []).map((digest) => ({
          ...digest,
          private_body: privateBodies.get(digest.id) ?? null,
        })) as DigestAdminRow[],
      );
    }
    setBusy(false);
  }, [supabase]);

  useEffect(() => {
    if (!supabase) return;

    void supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setAuthReady(true);
      if (data.session) void loadData();
    });

    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession);
      setAuthReady(true);
      if (nextSession) void loadData();
    });

    return () => data.subscription.unsubscribe();
  }, [loadData, supabase]);

  async function saveSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError("");
    setMessage("");

    const payload = {
      slug: draft.slug.trim() || slugFromName(draft.name),
      name: draft.name.trim(),
      home_url: draft.homeUrl.trim(),
      priority: draft.priority.trim() || "A",
      why: draft.why.trim(),
      include_patterns: lines(draft.includePatterns),
      allowed_hosts: lines(draft.allowedHosts),
      feed_urls: lines(draft.feedUrls),
      max_items: Number(draft.maxItems),
      max_feed_candidates: Number(draft.maxFeedCandidates),
    };

    const result = draft.id
      ? await supabase.from("sources").update(payload).eq("id", draft.id)
      : await supabase.from("sources").insert({ ...payload, enabled: true });

    if (result.error) setError(result.error.message);
    else {
      setDraft(EMPTY_SOURCE);
      setMessage(draft.id ? "Source updated." : "Source added.");
      await loadData();
    }
    setBusy(false);
  }

  async function toggleSource(source: SourceRow) {
    if (!supabase) return;
    setBusy(true);
    setError("");
    const { error: updateError } = await supabase
      .from("sources")
      .update({ enabled: !source.enabled })
      .eq("id", source.id);
    if (updateError) setError(updateError.message);
    else {
      setMessage(source.enabled ? "Source paused." : "Source enabled.");
      await loadData();
    }
    setBusy(false);
  }

  async function toggleDigest(digest: DigestAdminRow) {
    if (!supabase) return;
    setBusy(true);
    setError("");
    const publishing = digest.status === "draft";
    const { error: updateError } = await supabase
      .from("digests")
      .update({
        status: publishing ? "published" : "draft",
        published_at: publishing ? new Date().toISOString() : null,
      })
      .eq("id", digest.id);
    if (updateError) setError(updateError.message);
    else {
      setMessage(publishing ? "Digest published." : "Digest returned to draft.");
      await loadData();
    }
    setBusy(false);
  }

  if (!supabase) {
    return (
      <section className="admin-panel empty-state" aria-labelledby="admin-config-title">
        <p className="eyebrow">Configuration required</p>
        <h2 id="admin-config-title">Connect this site to Supabase.</h2>
        <p className="configuration-help">
          Set <code>NEXT_PUBLIC_<wbr />SUPABASE_<wbr />URL</code> and{" "}
          <code>NEXT_PUBLIC_<wbr />SUPABASE_<wbr />PUBLISHABLE_<wbr />KEY</code>.
        </p>
      </section>
    );
  }

  if (!authReady) return <p className="admin-status" role="status">Checking session…</p>;

  if (!session) {
    return (
      <section className="admin-panel auth-panel" aria-labelledby="admin-login-title">
        <p className="eyebrow">Session required</p>
        <h2 id="admin-login-title">Sign in with company Google.</h2>
        <p>Administrator role is checked by database policy.</p>
        <Link className="primary-link" href="/login/">Go to sign in</Link>
      </section>
    );
  }

  return (
    <div className="admin-console">
      <div className="admin-session">
        <p>Signed in as <strong>{session.user.email}</strong></p>
        <button className="text-button" type="button" onClick={() => void supabase.auth.signOut()}>
          Sign out
        </button>
      </div>

      {message ? <p className="form-success" role="status">{message}</p> : null}
      {error ? <p className="form-error" role="alert">{error}</p> : null}

      <section className="admin-section" aria-labelledby="source-editor-title">
        <div className="admin-section-heading">
          <div>
            <p className="eyebrow">Collection inputs</p>
            <h2 id="source-editor-title">Sources</h2>
          </div>
          <p>{sources.filter((source) => source.enabled).length} enabled / {sources.length} total</p>
        </div>

        <form className="source-form" onSubmit={saveSource}>
          <div className="source-basics">
            <label htmlFor="source-name">Source name</label>
            <input id="source-name" required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} />

            <label htmlFor="source-homepage">Homepage URL</label>
            <input id="source-homepage" required type="url" value={draft.homeUrl} onChange={(event) => setDraft({ ...draft, homeUrl: event.target.value })} />

            <label htmlFor="source-why">Why is this source useful?</label>
            <textarea id="source-why" placeholder="What ecommerce knowledge should the digest look for here?" value={draft.why} onChange={(event) => setDraft({ ...draft, why: event.target.value })} />
          </div>

          <details className="advanced-source-settings">
            <summary>
              Advanced collection settings
              <span>Optional</span>
            </summary>
            <p className="advanced-settings-intro">
              Leave these defaults alone unless a source is missing articles or following the wrong links.
            </p>
            <div className="form-grid">
              <label htmlFor="source-slug">
                Source ID
                <span className="field-help" id="source-slug-help">Auto-created from the name when blank. Lowercase letters, numbers, and hyphens only.</span>
                <input id="source-slug" aria-describedby="source-slug-help" pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={draft.slug} onChange={(event) => setDraft({ ...draft, slug: event.target.value })} />
              </label>
              <label htmlFor="source-max-items">
                Articles per run
                <span className="field-help" id="source-max-items-help">Maximum articles kept from this source in one collection run.</span>
                <input id="source-max-items" aria-describedby="source-max-items-help" required min="1" max="100" type="number" value={draft.maxItems} onChange={(event) => setDraft({ ...draft, maxItems: event.target.value })} />
              </label>
              <label htmlFor="source-feed-cap">
                Feed discovery limit
                <span className="field-help" id="source-feed-cap-help">Maximum auto-discovered RSS or Atom feeds tried before webpage fallback.</span>
                <input id="source-feed-cap" aria-describedby="source-feed-cap-help" required min="1" max="100" type="number" value={draft.maxFeedCandidates} onChange={(event) => setDraft({ ...draft, maxFeedCandidates: event.target.value })} />
              </label>
              <label htmlFor="source-feed-urls">
                Known RSS or Atom feeds
                <span className="field-help" id="source-feed-urls-help">Optional. One full feed URL per line. Collector auto-discovers feeds when blank.</span>
                <textarea id="source-feed-urls" aria-describedby="source-feed-urls-help" placeholder="https://example.com/feed.xml" value={draft.feedUrls} onChange={(event) => setDraft({ ...draft, feedUrls: event.target.value })} />
              </label>
              <label htmlFor="source-include-patterns">
                URL include fragments
                <span className="field-help" id="source-include-patterns-help">Optional plain text, not regex. Keep links whose URL contains any listed fragment.</span>
                <textarea id="source-include-patterns" aria-describedby="source-include-patterns-help" placeholder="/articles/" value={draft.includePatterns} onChange={(event) => setDraft({ ...draft, includePatterns: event.target.value })} />
              </label>
              <label htmlFor="source-allowed-hosts">
                Additional allowed domains
                <span className="field-help" id="source-allowed-hosts-help">Optional. Homepage domain is already allowed. Add another domain only when articles or feeds live there.</span>
                <textarea id="source-allowed-hosts" aria-describedby="source-allowed-hosts-help" placeholder="feeds.example.com" value={draft.allowedHosts} onChange={(event) => setDraft({ ...draft, allowedHosts: event.target.value })} />
              </label>
            </div>
          </details>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={busy}>{draft.id ? "Save source" : "Add source"}</button>
            {draft.id ? <button className="secondary-button" type="button" onClick={() => setDraft(EMPTY_SOURCE)}>Cancel edit</button> : null}
          </div>
        </form>

        <div className="source-list" aria-busy={busy}>
          {sources.map((source) => (
            <article className="source-row" key={source.id}>
              <div>
                <p className="source-status">{source.enabled ? "Enabled" : "Paused"}</p>
                <h3>{source.name}</h3>
                <a href={source.home_url} target="_blank" rel="noreferrer">{source.home_url}</a>
              </div>
              <div className="row-actions">
                <button className="secondary-button" type="button" onClick={() => setDraft(sourceDraft(source))}>Edit</button>
                <button className="secondary-button" type="button" onClick={() => void toggleSource(source)} disabled={busy}>{source.enabled ? "Pause" : "Enable"}</button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="admin-section" aria-labelledby="digest-review-title">
        <div className="admin-section-heading">
          <div>
            <p className="eyebrow">Publication queue</p>
            <h2 id="digest-review-title">Digests</h2>
          </div>
        </div>
        <div className="source-list">
          {digests.map((digest) => (
            <article className="source-row digest-admin-row" key={digest.id}>
              <div className="digest-admin-content">
                <p className="source-status">{digest.status} · {digest.published_on}</p>
                <h3>{digest.title}</h3>
                {digest.private_body?.actions?.length ? (
                  <details className="private-decision-guide">
                    <summary>
                      Private decision guide ({digest.private_body.actions.length})
                    </summary>
                    <p className="private-guide-intro">
                      Mellanni-only baselines and thresholds. Never shown on public digest pages.
                    </p>
                    {digest.private_body.actions.map((action) => (
                      <section className="private-action" key={action.id}>
                        <h4>{action.title}</h4>
                        <dl>
                          <div>
                            <dt>Entity</dt>
                            <dd>{action.privateDecision.entityIds.join(", ")}</dd>
                          </div>
                          <div>
                            <dt>Measured baseline</dt>
                            <dd>{action.privateDecision.baseline}</dd>
                          </div>
                          <div>
                            <dt>Guidance</dt>
                            <dd>{action.privateDecision.guidance}</dd>
                          </div>
                          <div>
                            <dt>KPI</dt>
                            <dd>{action.privateDecision.kpi}</dd>
                          </div>
                          <div>
                            <dt>Success</dt>
                            <dd>{action.privateDecision.successCondition}</dd>
                          </div>
                          <div>
                            <dt>Stop</dt>
                            <dd>{action.privateDecision.stopCondition}</dd>
                          </div>
                        </dl>
                      </section>
                    ))}
                  </details>
                ) : null}
              </div>
              <button className="secondary-button" type="button" onClick={() => void toggleDigest(digest)} disabled={busy}>
                {digest.status === "draft" ? "Publish" : "Return to draft"}
              </button>
            </article>
          ))}
          {!digests.length ? <p>No draft or published digests yet.</p> : null}
        </div>
      </section>
    </div>
  );
}
