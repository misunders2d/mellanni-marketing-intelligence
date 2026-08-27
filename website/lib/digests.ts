export type DigestSource = {
  id: string;
  name: string;
  url: string;
  note: string;
};

export type MemoryOutcome =
  | "consistent"
  | "contradicts"
  | "extends"
  | "no-relevant-record";

export type DigestMemory = {
  outcome: MemoryOutcome;
  comparison: string;
  decisionImpact: string;
};

export type DigestSkillReference = {
  uri: string;
  applicability: string;
  requiredInputs: readonly string[];
  intendedNextOperation: string;
};

export type DigestAction = {
  id: string;
  title: string;
  externalSignal: string;
  sourceIds: readonly string[];
  memory: DigestMemory;
  mellanniEvidence: {
    entityScope: string;
    conclusion: string;
    source: string;
    window: string;
    grain: string;
  };
  guidance: string;
  timebox: string;
  kpi: string;
  successCondition: string;
  stopCondition: string;
  confidence: "high" | "medium" | "low";
  limitations: readonly string[];
  skillReferences: readonly DigestSkillReference[];
};

export type DigestSignal = {
  id: string;
  title: string;
  externalSignal: string;
  sourceIds: readonly string[];
  memory: DigestMemory;
  whyItMatters: string;
  nextValidation: string;
  skillReferences: readonly DigestSkillReference[];
};

export type Digest = {
  slug: string;
  date: string;
  title: string;
  summary: string;
  topics: readonly string[];
  findings: readonly string[];
  actions: readonly DigestAction[];
  signals: readonly DigestSignal[];
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
  date: "2026-08-31",
  title: "Weekly marketing intelligence",
  summary:
    "Illustrative structure for decision-useful Mellanni guidance and broader ecommerce signals.",
  topics: ["Profitability", "Creator commerce"],
  findings: [],
  actions: [
    {
      id: "protect-margin-test",
      title: "Keep the next growth test inside the private margin guardrail",
      externalSignal:
        "Operators are increasingly evaluating channel growth on contribution rather than attributed revenue alone.",
      sourceIds: ["operator-source"],
      memory: {
        outcome: "no-relevant-record",
        comparison: "No historical record was specific enough to change this illustrative decision.",
        decisionImpact: "Use fresh private Mellanni evidence as the decision basis.",
      },
      mellanniEvidence: {
        entityScope: "Illustrative Mellanni portfolio",
        conclusion: "Private portfolio evidence supports an efficiency-first test; exact values and identifiers remain withheld.",
        source: "Mellanni first-party reporting",
        window: "Trailing review period, America/Los_Angeles",
        grain: "Portfolio and day",
      },
      guidance: "Run one bounded channel test and evaluate contribution alongside delivery and attributed demand.",
      timebox: "Two weekly review cycles",
      kpi: "Contribution efficiency versus the private baseline",
      successCondition: "Efficiency improves versus the private baseline while demand remains inside the approved operating range.",
      stopCondition: "Stop if contribution crosses the private guardrail or inventory can no longer support the test.",
      confidence: "medium",
      limitations: ["This sample contains no real Mellanni metric or identifier."],
      skillReferences: [
        {
          uri: "mellanni://skills/source-routing",
          applicability: "Choose the first-party source that owns each required business metric.",
          requiredInputs: ["entity scope", "metric", "time window"],
          intendedNextOperation: "Route the approved test readback to the correct Mellanni provider.",
        },
      ],
    },
  ],
  signals: [
    {
      id: "creator-commerce-signal",
      title: "Creator commerce is becoming a discovery layer",
      externalSignal:
        "Creator-led commerce is expanding beyond direct conversion into product discovery and later demand capture.",
      sourceIds: ["creator-source"],
      memory: {
        outcome: "consistent",
        comparison: "Signal matches historical guidance to separate discovery from measured conversion.",
        decisionImpact: "Keep it visible, but do not call it a Mellanni result without a bounded validation test.",
      },
      whyItMatters: "This may affect creative, attribution, and demand-capture choices across ecommerce channels, not only Amazon.",
      nextValidation: "Define a small creator-content holdout, then query branded demand and downstream conversion.",
      skillReferences: [
        {
          uri: "mellanni://skills/helium10-research",
          applicability: "Check whether external discovery coincides with branded or category search movement.",
          requiredInputs: ["seed keywords", "marketplace", "comparison window"],
          intendedNextOperation: "Compare bounded keyword discovery with first-party demand evidence.",
        },
      ],
    },
  ],
  sources: [
    {
      id: "operator-source",
      name: "Illustrative operator source",
      url: "https://example.com/operator-economics",
      note: "Illustrative direct evidence URL; replace it with a real source in an actual digest.",
    },
    {
      id: "creator-source",
      name: "Illustrative creator-commerce source",
      url: "https://example.com/creator-commerce",
      note: "Illustrative direct evidence URL; replace it with a real source in an actual digest.",
    },
  ],
  isSample: true,
};

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function objectValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object"
    ? value as Record<string, unknown>
    : {};
}

function text(value: unknown) {
  return typeof value === "string" ? value : "";
}

function digestMemory(value: unknown): DigestMemory | null {
  const candidate = objectValue(value);
  const outcome = candidate.outcome;
  if (
    outcome !== "consistent" &&
    outcome !== "contradicts" &&
    outcome !== "extends" &&
    outcome !== "no-relevant-record"
  ) return null;

  return {
    outcome,
    comparison: text(candidate.comparison),
    decisionImpact: text(candidate.decisionImpact),
  };
}

function digestSkillReferences(value: unknown): DigestSkillReference[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const candidate = objectValue(item);
    if (typeof candidate.uri !== "string") return [];
    return [{
      uri: candidate.uri,
      applicability: text(candidate.applicability),
      requiredInputs: stringList(candidate.requiredInputs),
      intendedNextOperation: text(candidate.intendedNextOperation),
    }];
  });
}

function digestActions(value: unknown): DigestAction[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const candidate = objectValue(item);
    const memory = digestMemory(candidate.memory);
    const evidence = objectValue(candidate.mellanniEvidence);
    if (!text(candidate.id) || !text(candidate.title) || !memory) return [];
    const confidence = candidate.confidence;
    return [{
      id: text(candidate.id),
      title: text(candidate.title),
      externalSignal: text(candidate.externalSignal),
      sourceIds: stringList(candidate.sourceIds),
      memory,
      mellanniEvidence: {
        entityScope: text(evidence.entityScope),
        conclusion: text(evidence.conclusion),
        source: text(evidence.source),
        window: text(evidence.window),
        grain: text(evidence.grain),
      },
      guidance: text(candidate.guidance),
      timebox: text(candidate.timebox),
      kpi: text(candidate.kpi),
      successCondition: text(candidate.successCondition),
      stopCondition: text(candidate.stopCondition),
      confidence: confidence === "high" || confidence === "medium" ? confidence : "low",
      limitations: stringList(candidate.limitations),
      skillReferences: digestSkillReferences(candidate.skillReferences),
    }];
  });
}

function digestSignals(value: unknown): DigestSignal[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const candidate = objectValue(item);
    const memory = digestMemory(candidate.memory);
    if (!text(candidate.id) || !text(candidate.title) || !memory) return [];
    return [{
      id: text(candidate.id),
      title: text(candidate.title),
      externalSignal: text(candidate.externalSignal),
      sourceIds: stringList(candidate.sourceIds),
      memory,
      whyItMatters: text(candidate.whyItMatters),
      nextValidation: text(candidate.nextValidation),
      skillReferences: digestSkillReferences(candidate.skillReferences),
    }];
  });
}

function digestSources(value: unknown): DigestSource[] {
  if (!Array.isArray(value)) return [];

  return value.flatMap((item, index) => {
    if (!item || typeof item !== "object") return [];
    const candidate = item as Record<string, unknown>;
    if (typeof candidate.name !== "string" || typeof candidate.url !== "string") {
      return [];
    }
    return [{
      id: typeof candidate.id === "string" ? candidate.id : `legacy-source-${index + 1}`,
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
    actions: digestActions(body.actions),
    signals: digestSignals(body.signals),
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
