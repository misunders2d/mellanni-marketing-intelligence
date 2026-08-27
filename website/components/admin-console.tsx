"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import type { Session } from "@supabase/supabase-js";
import { getBrowserSupabase } from "@/lib/supabase-browser";

const ADMIN_EMAIL = "sergey@mellanni.com";

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

    const [sourceResult, digestResult] = await Promise.all([
      supabase.from("sources").select("*").order("name"),
      supabase
        .from("digests")
        .select("id,slug,title,published_on,status")
        .order("published_on", { ascending: false }),
    ]);

    if (sourceResult.error || digestResult.error) {
      setError(sourceResult.error?.message ?? digestResult.error?.message ?? "Unable to load admin data.");
    } else {
      setSources((sourceResult.data ?? []) as SourceRow[]);
      setDigests((digestResult.data ?? []) as DigestAdminRow[]);
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

  async function sendMagicLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError("");
    setMessage("");

    const { error: authError } = await supabase.auth.signInWithOtp({
      email: ADMIN_EMAIL,
      options: { emailRedirectTo: window.location.origin + "/admin" },
    });

    if (authError) setError(authError.message);
    else setMessage("Sign-in link sent to " + ADMIN_EMAIL + ".");
    setBusy(false);
  }

  async function saveSource(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!supabase) return;
    setBusy(true);
    setError("");
    setMessage("");

    const payload = {
      slug: draft.slug.trim(),
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
        <p>Set `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.</p>
      </section>
    );
  }

  if (!authReady) return <p className="admin-status" role="status">Checking session…</p>;

  if (!session) {
    return (
      <section className="admin-panel auth-panel" aria-labelledby="admin-login-title">
        <p className="eyebrow">Admin authentication</p>
        <h2 id="admin-login-title">Sign in by email.</h2>
        <p>Access is restricted by database policy to {ADMIN_EMAIL}.</p>
        <form onSubmit={sendMagicLink}>
          <label htmlFor="admin-email">Admin email</label>
          <input id="admin-email" type="email" value={ADMIN_EMAIL} readOnly />
          <button className="primary-button" type="submit" disabled={busy}>
            {busy ? "Sending…" : "Email sign-in link"}
          </button>
        </form>
        {message ? <p className="form-success" role="status">{message}</p> : null}
        {error ? <p className="form-error" role="alert">{error}</p> : null}
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
          <div className="form-grid">
            <label>Slug<input required pattern="[a-z0-9]+(?:-[a-z0-9]+)*" value={draft.slug} onChange={(event) => setDraft({ ...draft, slug: event.target.value })} /></label>
            <label>Name<input required value={draft.name} onChange={(event) => setDraft({ ...draft, name: event.target.value })} /></label>
            <label className="wide-field">Homepage URL<input required type="url" value={draft.homeUrl} onChange={(event) => setDraft({ ...draft, homeUrl: event.target.value })} /></label>
            <label>Priority<input required value={draft.priority} onChange={(event) => setDraft({ ...draft, priority: event.target.value })} /></label>
            <label>Max items<input required min="1" max="100" type="number" value={draft.maxItems} onChange={(event) => setDraft({ ...draft, maxItems: event.target.value })} /></label>
            <label>Feed probe cap<input required min="1" max="100" type="number" value={draft.maxFeedCandidates} onChange={(event) => setDraft({ ...draft, maxFeedCandidates: event.target.value })} /></label>
            <label className="wide-field">Why this source<textarea value={draft.why} onChange={(event) => setDraft({ ...draft, why: event.target.value })} /></label>
            <label>Feed URLs<textarea placeholder="One per line" value={draft.feedUrls} onChange={(event) => setDraft({ ...draft, feedUrls: event.target.value })} /></label>
            <label>Include patterns<textarea placeholder="One per line" value={draft.includePatterns} onChange={(event) => setDraft({ ...draft, includePatterns: event.target.value })} /></label>
            <label>Allowed hosts<textarea placeholder="One per line" value={draft.allowedHosts} onChange={(event) => setDraft({ ...draft, allowedHosts: event.target.value })} /></label>
          </div>
          <div className="form-actions">
            <button className="primary-button" type="submit" disabled={busy}>{draft.id ? "Save source" : "Add source"}</button>
            {draft.id ? <button className="secondary-button" type="button" onClick={() => setDraft(EMPTY_SOURCE)}>Cancel edit</button> : null}
          </div>
        </form>

        <div className="source-list" aria-busy={busy}>
          {sources.map((source) => (
            <article className="source-row" key={source.id}>
              <div>
                <p className="source-status">{source.enabled ? "Enabled" : "Paused"} · Priority {source.priority}</p>
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
            <article className="source-row" key={digest.id}>
              <div>
                <p className="source-status">{digest.status} · {digest.published_on}</p>
                <h3>{digest.title}</h3>
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
