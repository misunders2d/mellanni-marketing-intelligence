# Mellanni Marketing Intelligence — Standalone Agent Guide

This guide explains the offline fixture path, with **zero Supabase access, zero Next.js website, and zero cloud database requirements**. It is not the live Mellanni workflow. Any agent with approved live Supabase access must use `UV_CACHE_DIR=/tmp/uv-cache uv run mellanni-weekly` to start and resume; never substitute this fixture/manual handoff for the live runner.

---

## 1. What This Skillset Is For

Ecommerce brands need continuous intelligence across Amazon, DTC, retail, advertising, creator commerce, operations, and marketplace policy. 

This skillset provides an automated pipeline that:
1. **Collects raw signals** from high-signal ecommerce sources (RSS/Atom feeds, industry blogs, podcasts, newsletters, and YouTube videos).
2. **Normalizes and journals content** into structured local Markdown files with a run manifest.
3. **Summarizes multimedia** (such as YouTube videos/podcasts) using multimodal AI.
4. **Synthesizes actionable intelligence** following strict editorial rules: distinguishing between immediate **Actions** (tactical brand moves with KPIs) and **External Signals** (broader market/platform trends).
5. **Delivers self-contained reports** in responsive single-file HTML or Markdown.

---

## 2. Standalone Architecture (Zero DB / Zero Website)

In standalone mode, everything runs locally on disk:

```text
[Sources Config] (config/sources.json)
       │
       ▼
[Python Collector] (python -m mellanni_marketing_intelligence)
       │
       ▼
[Local Journal] (/tmp/mellanni-marketing-journal/<run_id>/manifest.json + *.md source extracts)
       │
       ├─── [YouTube Helper] (scripts/youtube-summary.mjs via GOOGLE_API_KEY)
       │
       ▼
[Agent Synthesis] (Analyzes signals -> Extracts Actions & External Signals)
       │
       ▼
[HTML Generator] (scripts/generate_html_report.py)
       │
       ▼
[Standalone Deliverable] (report.html — viewable in any browser)
```

---

## 3. Environment & Required API Keys

### Requirements
- **Python**: `>=3.11` (managed with `uv` or standard `venv`)
- **Node.js**: `>=20.6` (for `--env-file` support in the YouTube summarization script)

### API Keys Needed
Create a local `.env` file in the project root:

```dotenv
# Required ONLY if running YouTube summarizer script:
GOOGLE_API_KEY=your-gemini-api-key

# (Optional overrides for YouTube model — defaults to Gemini 3.8 Flash agentic)
# YOUTUBE_SUMMARIZER_MODEL=gemini-3.8-flash
# YOUTUBE_SUMMARIZER_FALLBACK_MODEL=gemini-3.5-flash-lite
```

> **Note:** Zero Supabase keys, database credentials, or website tokens are needed in standalone mode.

---

## 4. Where to Put & Configure Sources

Sources are defined in JSON format. The default offline fixture is located at:
📁 `config/sources.json`

### Source Format Example
```json
{
  "sources": [
    {
      "slug": "marketplace-pulse",
      "name": "Marketplace Pulse",
      "home_url": "https://www.marketplacepulse.com/",
      "priority": "A",
      "why": "Independent, data-driven Amazon and marketplace structural changes.",
      "include_patterns": ["/articles/", "/news/"]
    },
    {
      "slug": "seller-sessions",
      "name": "Seller Sessions",
      "home_url": "https://sellersessions.com/podcast/",
      "priority": "A",
      "why": "Amazon conversion, ranking, listing, data, and AI workflows.",
      "include_patterns": ["/podcast/"],
      "feed_urls": ["https://sellersessions.libsyn.com/rss"],
      "allowed_hosts": ["sellersessions.libsyn.com"]
    }
  ]
}
```

### Pre-Configured Pilot Sources
The included `config/sources.json` comes pre-configured with 13 top ecommerce & marketplace intelligence sources:
- **Marketplace Pulse** (Amazon & marketplace data)
- **Practical Ecommerce** (Paid media, CRO, analytics)
- **DTC Newsletter** (Growth tactics, creative, landing pages)
- **Nik Sharma Newsletter** (Operator lessons, conversion, DTC strategy)
- **Sell on Amazon Announcements** (Official Amazon Seller Central announcements)
- **Amazon Ads News** (Official Amazon Ads, DSP, AMC, AI Prompts updates)
- **Marketing Operators** (Ecommerce growth & experimentation)
- **9 Operators** (Ecommerce leadership & scaling)
- **Limited Supply** (DTC brand strategy & economics)
- **AM/PM Podcast** (Amazon seller strategy & operations)
- **The PPC Den** (Amazon PPC structure & optimization)
- **Seller Sessions** (Amazon SEO, ranking, AI workflows)
- **The Smartest Amazon Seller** (Amazon brand strategy)

You can add any new blogs, RSS/Atom feeds, or podcast feeds directly to `config/sources.json` or pass a custom config via `--config <path>`.

---

## 5. How to Run the Offline Fixture Pipeline

For live Mellanni collection, YouTube processing, synthesis handoff, draft write,
readback, and linked proof, stop here and use the weekly runner:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run mellanni-weekly
```

The steps below are only for standalone/offline fixture output. They do not create
or publish a live Mellanni digest.

### Step 1: Install Python Environment
Using `uv` (recommended):
```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
```

Repository policy requires the locked `uv` environment; do not install with bare system `pip` or `python`.

### Step 2: Run Offline Fixture Collection
Fetch the last 8 days of content from the checked-in fixture configuration:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence --since-days 8
```

Target specific sources while debugging:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence --source marketplace-pulse --source amazon-ads-news
```

Output is written to `/tmp/mellanni-marketing-journal/<run_id>/`:
- `/tmp/mellanni-marketing-journal/<run_id>/manifest.json` — Immutable manifest v3 with source status, item metadata, and SHA-256 for every collected artifact.
- `/tmp/mellanni-marketing-journal/<run_id>/items/<source_slug>/<item_hash>.md` — Private `0600` Markdown extracts of untrusted external articles/episodes.

### Step 3: Summarize Every YouTube Video
When the manifest contains YouTube items, run the Gemini 3.8 Flash agentic video summarizer across the full manifest. The command writes one JSON and Markdown artifact per video and exits nonzero if any video fails:
```bash
node --env-file=.env scripts/youtube-summary.mjs \
  --manifest /tmp/mellanni-marketing-journal/RUN_ID/manifest.json

# Optional focus:
node --env-file=.env scripts/youtube-summary.mjs \
  --manifest /tmp/mellanni-marketing-journal/RUN_ID/manifest.json \
  --focus "FOCUS QUESTION"
```

Output stays under `/tmp/mellanni-marketing-journal/RUN_ID/youtube/`. Helper leaves `manifest.json` immutable and writes a run/hash-bound sidecar plus atomic per-episode Markdown and JSON artifacts, each with its own SHA-256. Require `expected == succeeded` and `failed == 0` before synthesis. Review every episode separately; never substitute one representative video or collapse week into one sentence. In evidence packet, record one included/excluded `itemReviews` decision for every manifest item.

---

## 6. Agent Synthesis & Editorial Rules

When an AI agent analyzes the collected articles and notes in `/tmp/mellanni-marketing-journal/<run_id>/`, it must synthesize findings following this editorial framework:

### Two Core Item Types:

#### 1. Mellanni Actions (`[ACTION]`)
Concrete, high-confidence recommendations with specific execution details:
- **Title**: Crisp operational instruction (e.g., *Audit hero ASIN backend attributes for Alexa Shopping*).
- **Signal**: Exactly what external signal triggered this action.
- **Guidance**: Concrete tactical instructions (who/what/how).
- **KPI**: Measurable metric (e.g., Conversion rate, ACoS, prompt engagement).
- **Timebox & Milestones**: Realistic timeframe (e.g., 2 weeks).
- **Success & Stop Conditions**: Clear thresholds when to double down or roll back.

#### 2. External Signals (`[SIGNAL]`)
Valuable market trends, algorithm shifts, platform policy changes, or competitor strategies:
- **Title**: Clear summary of the trend/change.
- **Signal**: What happened and who reported it.
- **Relevance**: Why it matters to ecommerce operators and brands.
- **Next Validation**: What data or test is needed before promoting this to an Action.

---

## 7. Delivering Results in HTML

To present the intelligence in a clean, professional, self-contained format that can be shared or opened in any browser:

### Option A: Use the Bundled Generator
Write your synthesized digest to a Markdown file (e.g., `digest.md`), then run:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/generate_html_report.py digest.md -o report.html --title "Weekly Ecommerce Intelligence Digest"
```

A schema-v2 digest JSON renders through the same member-visible projection the website uses (Actions, External Signals, sources; private decision detail, query refs, and memory refs are never rendered). It accepts either a `digest.json` input or a stored digest row whose `body` is the projected object:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/generate_html_report.py digest.json -o report.html
```

Write `report.html` to a temporary directory; it is a run artifact, not a repository file.

### Option B: HTML Report Template Structure
The resulting `report.html` is a single static HTML file with embedded responsive CSS:
- Works 100% offline (no CDN or external dependencies).
- Automatically supports Dark and Light mode.
- Formats `[ACTION]` and `[SIGNAL]` tags with distinct styled badge cards.
- Preserves tables, code snippets, blockquotes, and source links.

---

## 8. Summary of Files in This Skillset

| Path | Purpose |
|---|---|
| `STANDALONE.md` | This standalone runbook & guide |
| `config/sources.json` | 13 pre-configured offline ecommerce intelligence sources |
| `src/mellanni_marketing_intelligence/` | Core Python collector and feed discovery engine |
| `scripts/youtube-summary.mjs` | Multimodal Gemini YouTube video summarizer |
| `scripts/generate_html_report.py` | Standalone zero-dependency HTML report generator |
| `skills/mellanni-marketing-operator/` | Editorial rules, operations reference, and schemas |
| `schemas/` | Evidence packet & digest validation JSON schemas |
| `pyproject.toml` | Python project specification (`jsonschema` dependency) |
| `.env.example` | Template for `GOOGLE_API_KEY` |
