import Link from "next/link";
import { digestFindings, digestHref, formatDigestDate, type Digest } from "@/lib/digests";

function monthLabel(date: string) {
  return new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" })
    .format(new Date(date + "T12:00:00Z"));
}

export function DigestMonthList({ digests }: { digests: readonly Digest[] }) {
  const months = new Map<string, Digest[]>();
  for (const digest of digests) {
    const key = digest.date.slice(0, 7);
    months.set(key, [...(months.get(key) ?? []), digest]);
  }

  if (!months.size) {
    return (
      <div className="empty-state">
        <p className="eyebrow">No published digest</p>
        <h2 className="empty-title">Nothing has been published yet.</h2>
      </div>
    );
  }

  return (
    <div className="month-list">
      {[...months.entries()].map(([key, items]) => (
        <section className="month-group" key={key} aria-labelledby={`month-${key}`}>
          <h2 id={`month-${key}`}>{monthLabel(items[0].date)}</h2>
          <ol>
            {items.map((digest) => {
              const count = digestFindings(digest).length;
              return (
                <li key={digest.slug}>
                  <time dateTime={digest.date}>{formatDigestDate(digest.date)}</time>
                  <div>
                    <Link href={digestHref(digest.slug)}>{digest.title}</Link>
                    <p>{digest.summary}</p>
                  </div>
                  <span className="month-count">{count ? `${count} ${count === 1 ? "item" : "items"}` : "Legacy"}</span>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
