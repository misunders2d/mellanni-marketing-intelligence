import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DigestView } from "@/components/digest-view";
import { getPublishedDigestBySlug } from "@/lib/supabase-public";

type DigestPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: DigestPageProps): Promise<Metadata> {
  const { slug } = await params;
  const digest = await getPublishedDigestBySlug(slug);

  if (!digest) return { title: "Digest not found" };

  return {
    title: digest.title,
    description: digest.summary,
    openGraph: {
      title: digest.title,
      description: digest.summary,
      type: "article",
      publishedTime: digest.date,
    },
  };
}

export default async function DigestPage({ params }: DigestPageProps) {
  const { slug } = await params;
  const digest = await getPublishedDigestBySlug(slug);

  if (!digest) notFound();

  return (
    <article className="shell digest-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link href="/">Home</Link>
        <span aria-hidden="true">/</span>
        <span>Weekly digest</span>
      </nav>

      <DigestView digest={digest} />

      <footer className="digest-footer">
        <p>Continue through the archive by signal or publication date.</p>
        <div>
          <Link className="primary-link" href="/search">Search digests</Link>
          <Link className="text-link" href="/calendar">Browse by month</Link>
        </div>
      </footer>
    </article>
  );
}
