import Link from "next/link";
import { formatDigestDate, type Digest } from "@/lib/digests";

export function DigestCard({ digest }: { digest: Digest }) {
  return (
    <article className="digest-card">
      <div className="digest-card-meta">
        <time dateTime={digest.date}>{formatDigestDate(digest.date)}</time>
        {digest.isSample ? <span className="sample-marker">Sample edition</span> : null}
      </div>
      <div className="digest-card-body">
        <div>
          <h3>
            <Link href={"/digests/" + digest.slug}>{digest.title}</Link>
          </h3>
          <p>{digest.summary}</p>
        </div>
        <ul className="topic-list" aria-label="Topics">
          {digest.topics.map((topic) => (
            <li key={topic}>{topic}</li>
          ))}
        </ul>
      </div>
      <Link className="text-link" href={"/digests/" + digest.slug}>
        Read this digest <span aria-hidden="true">→</span>
      </Link>
    </article>
  );
}
