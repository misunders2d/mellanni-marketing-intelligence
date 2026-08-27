import type { Metadata } from "next";
import type { ReactNode } from "react";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Mellanni Marketing Intelligence",
    template: "%s | Mellanni Marketing Intelligence",
  },
  description:
    "Weekly editorial briefings that connect sales economics, advertising, inventory, and search behavior.",
  applicationName: "Mellanni Marketing Intelligence",
  openGraph: {
    title: "Mellanni Marketing Intelligence",
    description:
      "Weekly editorial briefings that connect sales economics, advertising, inventory, and search behavior.",
    type: "website",
    locale: "en_US",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <SiteHeader />
        <main id="main-content">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
