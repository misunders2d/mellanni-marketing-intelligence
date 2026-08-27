import type { Digest } from "@/lib/digests";

type WeightedField = {
  text: string;
  weight: number;
};

export type IndexedDigest = {
  digest: Digest;
  fields: readonly WeightedField[];
  fullText: string;
};

export type DigestSearchResult = {
  digest: Digest;
  score: number;
};

function normalize(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLocaleLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

export function indexDigest(digest: Digest): IndexedDigest {
  const fields = [
    { text: normalize(digest.title), weight: 8 },
    { text: normalize(digest.summary), weight: 6 },
    ...digest.topics.map((topic) => ({ text: normalize(topic), weight: 7 })),
    ...digest.findings.map((finding) => ({ text: normalize(finding), weight: 4 })),
    ...digest.actions.flatMap((action) => [
      { text: normalize(action.title), weight: 7 },
      { text: normalize(action.externalSignal), weight: 5 },
      { text: normalize(action.guidance), weight: 6 },
      { text: normalize(action.mellanniEvidence.conclusion), weight: 4 },
    ]),
    ...digest.signals.flatMap((signal) => [
      { text: normalize(signal.title), weight: 7 },
      { text: normalize(signal.externalSignal), weight: 5 },
      { text: normalize(signal.whyItMatters), weight: 5 },
    ]),
    ...digest.sources.map((source) => ({ text: normalize(source.name), weight: 5 })),
  ];

  return {
    digest,
    fields,
    fullText: fields.map((field) => field.text).join(" "),
  };
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

export function searchDigestIndex(
  index: readonly IndexedDigest[],
  query: string,
): DigestSearchResult[] {
  const normalizedQuery = normalize(query);
  if (!normalizedQuery) return [];

  const terms = normalizedQuery.split(" ");
  const results: DigestSearchResult[] = [];

  for (const entry of index) {
    let score = entry.fullText.includes(normalizedQuery) ? 120 : 0;
    let matchedAllTerms = true;

    for (const term of terms) {
      let bestTermScore = 0;
      for (const field of entry.fields) {
        bestTermScore = Math.max(bestTermScore, termScore(term, field));
      }

      if (!bestTermScore) {
        matchedAllTerms = false;
        break;
      }
      score += bestTermScore;
    }

    if (matchedAllTerms) results.push({ digest: entry.digest, score });
  }

  return results.sort(
    (left, right) =>
      right.score - left.score ||
      right.digest.date.localeCompare(left.digest.date),
  );
}
