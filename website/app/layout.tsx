import type { Metadata } from "next";
import { Source_Sans_3, Source_Serif_4 } from "next/font/google";
import type { ReactNode } from "react";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import "./globals.css";

const displayFace = Source_Serif_4({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-display-face",
});

const bodyFace = Source_Sans_3({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-body-face",
});

const description =
  "Weekly briefings that turn external ecommerce signals into Mellanni actions, checked against company data and Professional Memory.";

export const metadata: Metadata = {
  title: {
    default: "Mellanni Marketing Intelligence",
    template: "%s | Mellanni Marketing Intelligence",
  },
  description,
  applicationName: "Mellanni Marketing Intelligence",
  openGraph: {
    title: "Mellanni Marketing Intelligence",
    description,
    type: "website",
    locale: "en_US",
  },
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${displayFace.variable} ${bodyFace.variable}`}>
      <body>
        <a className="skip-link" href="#main-content">Skip to content</a>
        <SiteHeader />
        <main id="main-content">{children}</main>
        <SiteFooter />
      </body>
    </html>
  );
}
