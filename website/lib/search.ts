import { digestHref, type Digest } from "@/lib/digests";

type WeightedField = {
  text: string;
  weight: number;
};

export type SearchHit = {
  key: string;
  kind: "digest" | "action" | "signal";
  digest: Digest;
  title: string;
  snippet: string;
  href: string;
};

export type IndexedEntry = {
  hit: SearchHit;
  fields: readonly WeightedField[];
  fullText: string;
};

export type SearchResult = SearchHit & { score: number };

const MAX_RESULTS = 50;

function normalize(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function entry(hit: SearchHit, fields: { text: string; weight: number }[]): IndexedEntry {
  const normalized = fields
    .map((field) => ({ text: normalize(field.text), weight: field.weight }))
    .filter((field) => field.text);
  return { hit, fields: normalized, fullText: normalized.map((field) => field.text).join(" ") };
}

/** One entry per digest plus one per Action and External Signal, so hits deep-link to the finding. */
export function indexDigests(digests: readonly Digest[]): IndexedEntry[] {
  return digests.flatMap((digest) => {
    const sourceName = (ids: readonly string[]) =>
      ids.flatMap((id) => digest.sources.filter((source) => source.id === id).map((source) => ({ text: source.name, weight: 4 })));
    const digestEntry = entry(
      {
        key: digest.slug,
        kind: "digest",
        digest,
        title: digest.title,
        snippet: digest.summary,
        href: digestHref(digest.slug),
      },
      [
        { text: digest.title, weight: 8 },
        { text: digest.summary, weight: 6 },
        ...digest.topics.map((topic) => ({ text: topic, weight: 7 })),
        ...digest.findings.map((finding) => ({ text: finding, weight: 4 })),
        ...digest.sources.map((source) => ({ text: source.name, weight: 3 })),
      ],
    );
    const actionEntries = digest.actions.map((action) => entry(
      {
        key: `${digest.slug}#${action.id}`,
        kind: "action",
        digest,
        title: action.title,
        snippet: action.guidance,
        href: digestHref(digest.slug, action.id),
      },
      [
        { text: action.title, weight: 8 },
        { text: action.guidance, weight: 6 },
        { text: action.externalSignal, weight: 5 },
        { text: action.mellanniEvidence.conclusion, weight: 4 },
        { text: action.kpi, weight: 4 },
        ...sourceName(action.sourceIds),
      ],
    ));
    const signalEntries = digest.signals.map((signal) => entry(
      {
        key: `${digest.slug}#${signal.id}`,
        kind: "signal",
        digest,
        title: signal.title,
        snippet: signal.whyItMatters || signal.externalSignal,
        href: digestHref(digest.slug, signal.id),
      },
      [
        { text: signal.title, weight: 8 },
        { text: signal.externalSignal, weight: 5 },
        { text: signal.whyItMatters, weight: 5 },
        { text: signal.nextValidation, weight: 4 },
        ...sourceName(signal.sourceIds),
      ],
    ));
    return [digestEntry, ...actionEntries, ...signalEntries];
  });
}

function editDistance(left: string, right: string) {
  if (left === right) return 0;
  if (!left.length) return right.length;
  if (!right.length) return left.length;

  let previous = Array.from({ length: right.length + 1 }, (_, index) => index);
  let current = new Array<number>(right.length + 1);

  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    current[0] = leftIndex;

    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      const substitution =
        left[leftIndex - 1] === right[rightIndex - 1] ? 0 : 1;
      current[rightIndex] = Math.min(
        current[rightIndex - 1] + 1,
        previous[rightIndex] + 1,
        previous[rightIndex - 1] + substitution,
      );
    }

    [previous, current] = [current, previous];
  }

  return previous[right.length];
}

function termScore(term: string, field: WeightedField) {
  if (field.text === term) return 20 * field.weight;
  if (field.text.includes(term)) return 12 * field.weight;

  const words = field.text.split(" ");
  let best = 0;

  for (const word of words) {
    if (word.startsWith(term) || term.startsWith(word)) {
      best = Math.max(best, 9 * field.weight);
      continue;
    }

    if (term.length < 4 || word.length < 4) continue;

    const distance = editDistance(term, word);
    const allowance = Math.max(term.length, word.length) > 7 ? 2 : 1;
    if (distance <= allowance) {
      best = Math.max(best, (7 - distance) * field.weight);
    }
  }

  return best;
}

export function searchIndex(
  index: readonly IndexedEntry[],
  query: string,
): SearchResult[] {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) return [];

  const terms = normalizedQuery.split(" ");
  const results: SearchResult[] = [];

  for (const indexed of index) {
    let score = indexed.fullText.includes(normalizedQuery) ? 120 : 0;
    let matchedAllTerms = true;

    for (const term of terms) {
      let bestTermScore = 0;
      for (const field of indexed.fields) {
        bestTermScore = Math.max(bestTermScore, termScore(term, field));
      }

      if (!bestTermScore) {
        matchedAllTerms = false;
        break;
      }
      score += bestTermScore;
    }

    if (matchedAllTerms) results.push({ ...indexed.hit, score });
  }

  return results
    .sort(
      (left, right) =>
        right.score - left.score ||
        right.digest.date.localeCompare(left.digest.date),
    )
    .slice(0, MAX_RESULTS);
}
