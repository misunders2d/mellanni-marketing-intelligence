import Link from "next/link";

const navigation = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/calendar", label: "Calendar" },
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="wordmark" href="/" aria-label="Mellanni Marketing Intelligence home">
          <span className="wordmark-kicker">Mellanni</span>
          <span className="wordmark-title">Marketing Intelligence</span>
        </Link>
        <nav aria-label="Primary navigation">
          <ul className="nav-list">
            {navigation.map((item) => (
              <li key={item.href}>
                <Link href={item.href}>{item.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
