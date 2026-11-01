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
  status?: "draft" | "published";
};

export type DigestFinding =
  | { kind: "action"; item: DigestAction }
  | { kind: "signal"; item: DigestSignal };

export function digestFindings(digest: Digest): DigestFinding[] {
  return [
    ...digest.actions.map((item) => ({ kind: "action" as const, item })),
    ...digest.signals.map((item) => ({ kind: "signal" as const, item })),
  ];
}

/** Memory notes worth showing to readers: they change or extend a prior decision. */
export function isNotableMemory(memory: DigestMemory) {
  return memory.outcome === "contradicts" || memory.outcome === "extends";
}

export function digestHref(slug: string, findingId?: string) {
  return `/digests/${slug}/${findingId ? `#${findingId}` : ""}`;
}

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
