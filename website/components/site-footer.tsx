import Link from "next/link";

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <div className="shell footer-inner">
        <p>
          <strong>Mellanni Marketing Intelligence</strong>
          <span>Weekly evidence, read in context.</span>
        </p>
        <nav aria-label="Footer navigation">
          <Link href="/search">Search the archive</Link>
          <Link href="/calendar">Browse by date</Link>
        </nav>
      </div>
    </footer>
  );
}
