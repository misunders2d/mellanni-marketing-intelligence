# Mellanni Marketing Intelligence — Standalone Agent Guide

This guide explains what this skillset is for and how any AI agent or operator can run the entire marketing intelligence pipeline **standalone** — with **zero Supabase access, zero Next.js website, and zero cloud database requirements**.

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
[Local Journal] (journal/<run_id>/manifest.json + *.md source extracts)
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
- **Node.js**: `>=18` (for YouTube summarization script)

### API Keys Needed
Create a local `.env` file in the project root:

```dotenv
# Required ONLY if running YouTube summarizer script:
GOOGLE_API_KEY=your-gemini-api-key

# (Optional overrides for YouTube model — defaults to Gemini 3.7 Flash agentic)
# YOUTUBE_SUMMARIZER_MODEL=gemini-3.7-flash
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
The included `config/sources.json` comes pre-configured with 12 top ecommerce & marketplace intelligence sources:
- **Marketplace Pulse** (Amazon & marketplace data)
- **Practical Ecommerce** (Paid media, CRO, analytics)
- **DTC Newsletter** (Growth tactics, creative, landing pages)
- **Nik Sharma Newsletter** (Operator lessons, conversion, DTC strategy)
- **Sell on Amazon Announcements** (Official Amazon Seller Central announcements)
- **Amazon Ads News** (Official Amazon Ads, DSP, AMC, AI Prompts updates)
- **Marketing Operators** (Ecommerce growth & experimentation)
- **9 Operators** (Ecommerce leadership & scaling)
- **Limited Supply** (DTC brand strategy & economics)
- **The PPC Den** (Amazon PPC structure & optimization)
- **Seller Sessions** (Amazon SEO, ranking, AI workflows)
- **The Smartest Amazon Seller** (Amazon brand strategy)

You can add any new blogs, RSS/Atom feeds, or podcast feeds directly to `config/sources.json` or pass a custom config via `--config <path>`.

---

## 5. How to Run the Pipeline

### Step 1: Install Python Environment
Using `uv` (recommended):
```bash
UV_CACHE_DIR=/tmp/uv-cache uv sync --locked
```

Or using standard `pip`:
```bash
pip install -e .
```

### Step 2: Run Collection
Fetch the last 8 days of content across all configured sources:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence --since-days 8
```

Target specific sources while debugging:
```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python -m mellanni_marketing_intelligence --source marketplace-pulse --source amazon-ads-news
```

Output is written to `journal/<run_id>/`:
- `journal/<run_id>/manifest.json` — Machine-readable summary of fetched sources, counts, and status.
- `journal/<run_id>/<source_slug>/<item_hash>.md` — Clean Markdown extracts of individual articles/episodes.

### Step 3: Summarize YouTube Videos (Optional)
If a source item references a YouTube video or podcast episode, use the Gemini 3.7 Flash agentic video summarizer:
```bash
# Agentic video processing (default — analyzes video understanding steps):
node --env-file=.env scripts/youtube-summary.mjs "https://www.youtube.com/watch?v=VIDEO_ID" "Focus question or topic"

# Optional static mode (for short latency-sensitive clips or frame-level coverage):
node --env-file=.env scripts/youtube-summary.mjs "https://www.youtube.com/watch?v=VIDEO_ID" --static
```

---

## 6. Agent Synthesis & Editorial Rules

When an AI agent analyzes the collected articles and notes in `journal/<run_id>/`, it must synthesize findings following this editorial framework:

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
python scripts/generate_html_report.py digest.md -o report.html --title "Weekly Ecommerce Intelligence Digest"
```

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
| `config/sources.json` | 12+ pre-configured ecommerce intelligence sources |
| `src/mellanni_marketing_intelligence/` | Core Python collector and feed discovery engine |
| `scripts/youtube-summary.mjs` | Multimodal Gemini YouTube video summarizer |
| `scripts/generate_html_report.py` | Standalone zero-dependency HTML report generator |
| `skills/mellanni-marketing-operator/` | Editorial rules, operations reference, and schemas |
| `schemas/` | Evidence packet & digest validation JSON schemas |
| `pyproject.toml` | Python project specification (`jsonschema` dependency) |
| `.env.example` | Template for `GOOGLE_API_KEY` |
