import Link from "next/link";

export default function NotFound() {
  return (
    <section className="shell not-found">
      <p className="eyebrow">404 / Archive note</p>
      <h1>That briefing is not in the archive.</h1>
      <p>The address may have changed, or the digest may not have been published.</p>
      <Link className="primary-link" href="/">Return to the latest digest</Link>
    </section>
  );
}
