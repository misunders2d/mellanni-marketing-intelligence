import Link from "next/link";
import { AuthControls } from "@/components/auth-controls";

const navigation = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/calendar", label: "Calendar" },
  { href: "/admin", label: "Admin" },
];

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="wordmark" href="/" aria-label="Mellanni Marketing Intelligence home">
          <span className="wordmark-kicker">Mellanni</span>
          <span className="wordmark-title">Marketing Intelligence</span>
        </Link>
        <div className="header-actions">
          <nav aria-label="Primary navigation">
            <ul className="nav-list">
              {navigation.map((item) => (
                <li key={item.href}>
                  <Link href={item.href}>{item.label}</Link>
                </li>
              ))}
            </ul>
          </nav>
          <AuthControls />
        </div>
      </div>
    </header>
  );
}
