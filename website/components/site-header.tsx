import Link from "next/link";
import { AuthControls } from "@/components/auth-controls";
import { NavLinks } from "@/components/nav-links";
import { getMemberRole } from "@/lib/supabase-public";

const READER_NAVIGATION = [
  { href: "/", label: "Home" },
  { href: "/search", label: "Search" },
  { href: "/calendar", label: "Archive" },
];

export async function SiteHeader() {
  // Display only: proxy.ts and RLS still enforce admin access.
  const role = await getMemberRole();
  const navigation = role === "admin"
    ? [...READER_NAVIGATION, { href: "/admin", label: "Admin" }]
    : READER_NAVIGATION;

  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="wordmark" href="/" aria-label="Mellanni Marketing Intelligence home">
          <span className="wordmark-kicker">Mellanni</span>
          <span className="wordmark-title">Marketing Intelligence</span>
        </Link>
        <div className="header-actions">
          {role ? (
            <nav aria-label="Primary navigation">
              <NavLinks items={navigation} />
            </nav>
          ) : null}
          <AuthControls />
        </div>
      </div>
    </header>
  );
}
