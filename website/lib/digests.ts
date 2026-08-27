export type DigestSource = {
  name: string;
  url: string;
  note: string;
};

export type Digest = {
  slug: string;
  date: string;
  title: string;
  summary: string;
  topics: readonly string[];
  findings: readonly string[];
  sources: readonly DigestSource[];
  isSample?: boolean;
};

export type DigestRow = {
  slug: string;
  published_on: string;
  title: string;
  summary: string;
  body: unknown;
};

export const sampleDigest: Digest = {
  slug: "sample-weekly-intelligence-brief",
  date: "2026-08-24",
  title: "One weekly review, four connected lenses",
  summary:
    "A sample edition showing how sales economics, advertising, inventory, and search behavior can be read together without turning an early signal into a claim.",
  topics: ["Profitability", "Amazon Ads", "Inventory", "Keyword intelligence"],
  findings: [
    "Begin with sales economics: review gross and net sales, fees, promotions, and product-level contribution together before interpreting top-line movement.",
    "Read advertising in context: use first-party Amazon Ads reporting, separate delivery from attributed outcomes, and account for reporting windows before drawing a conclusion.",
    "Check inventory before diagnosing demand: stock availability and stockout risk can change what conversion and sales patterns appear to mean.",
    "Reconcile keyword discovery with Search Query Performance behavior so reach, clicks, and purchase intent remain distinct signals.",
  ],
  sources: [
    {
      name: "Amazon Ads reporting documentation",
      url: "https://advertising.amazon.com/API/docs/en-us/guides/reporting/v3/overview",
      note: "First-party reporting concepts and report workflow reference.",
    },
    {
      name: "Selling Partner API Reports reference",
      url: "https://developer-docs.amazon.com/sp-api/docs/reports-api-v2021-06-30-reference",
      note: "Official report retrieval and report type reference.",
    },
    {
      name: "Amazon Search Query Performance dashboard",
      url: "https://sellercentral.amazon.com/search-query-performance/dashboard",
      note: "Seller Central source for search funnel behavior.",
    },
  ],
  isSample: true,
};

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function digestSources(value: unknown): DigestSource[] {
  if (!Array.isArray(value)) return [];

  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const candidate = item as Record<string, unknown>;
    if (typeof candidate.name !== "string" || typeof candidate.url !== "string") {
      return [];
    }
    return [{
      name: candidate.name,
      url: candidate.url,
      note: typeof candidate.note === "string" ? candidate.note : "",
    }];
  });
}

export function digestFromRow(row: DigestRow): Digest {
  const body = row.body && typeof row.body === "object"
    ? row.body as Record<string, unknown>
    : {};

  return {
    slug: row.slug,
    date: row.published_on,
    title: row.title,
    summary: row.summary,
    topics: stringList(body.topics),
    findings: stringList(body.findings),
    sources: digestSources(body.sources),
    isSample: body.isSample === true,
  };
}

export function formatDigestDate(date: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(date + "T12:00:00Z"));
}
