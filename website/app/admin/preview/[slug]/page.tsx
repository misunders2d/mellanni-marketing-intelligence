import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { DigestView } from "@/components/digest-view";
import { getDigestForAdminPreview } from "@/lib/supabase-public";

type PreviewPageProps = {
  params: Promise<{ slug: string }>;
};

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Digest preview",
  robots: { index: false, follow: false },
};

export default async function DigestPreviewPage({ params }: PreviewPageProps) {
  const { slug } = await params;
  // proxy.ts limits /admin/* to admins; RLS returns no draft rows to anyone else.
  const preview = await getDigestForAdminPreview(slug);

  if (!preview) notFound();

  return (
    <article className="shell digest-page">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link href="/admin/">Admin</Link>
        <span aria-hidden="true">/</span>
        <span>Preview</span>
      </nav>
      <DigestView
        digest={preview.digest}
        banner={(
          <aside className="preview-banner" role="note" aria-label="Preview status">
            <p className="eyebrow">Admin preview · {preview.status}</p>
            <p>
              {preview.status === "draft"
                ? "Readers cannot see this draft. This is exactly how it will render once published."
                : "This digest is published. Readers see this page at its public address."}
            </p>
            <Link className="text-link" href="/admin/">Back to the publication queue</Link>
          </aside>
        )}
      />
    </article>
  );
}
