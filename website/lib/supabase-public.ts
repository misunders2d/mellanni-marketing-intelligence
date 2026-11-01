import "server-only";

import { digestFromRow, type Digest, type DigestRow } from "@/lib/digests";
import { createServerSupabaseClient } from "@/lib/supabase-server";

const PUBLIC_FIELDS = "slug,published_on,title,summary,body";

/** Database read failure. Rendered by the error boundary, never as an empty archive. */
export class DigestLoadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DigestLoadError";
  }
}

export async function getPublishedDigests(): Promise<Digest[]> {
  const client = await createServerSupabaseClient();

  const { data, error } = await client
    .from("digests")
    .select(PUBLIC_FIELDS)
    .eq("status", "published")
    .order("published_on", { ascending: false });

  if (error) {
    console.error("Unable to load published digests:", error.message);
    throw new DigestLoadError("Published digests could not be loaded.");
  }

  return (data as DigestRow[] | null)?.map(digestFromRow) ?? [];
}

export async function getPublishedDigestBySlug(slug: string): Promise<Digest | undefined> {
  const client = await createServerSupabaseClient();

  const { data, error } = await client
    .from("digests")
    .select(PUBLIC_FIELDS)
    .eq("status", "published")
    .eq("slug", slug)
    .maybeSingle();

  if (error) {
    console.error("Unable to load published digest:", error.message);
    throw new DigestLoadError("This digest could not be loaded.");
  }

  return data ? digestFromRow(data as DigestRow) : undefined;
}

/** Admin-only draft or published digest. RLS returns nothing for non-admins. */
export async function getDigestForAdminPreview(
  slug: string,
): Promise<{ digest: Digest; status: "draft" | "published" } | undefined> {
  const client = await createServerSupabaseClient();

  const { data, error } = await client
    .from("digests")
    .select(`${PUBLIC_FIELDS},status`)
    .eq("slug", slug)
    .maybeSingle();

  if (error) {
    console.error("Unable to load digest preview:", error.message);
    throw new DigestLoadError("This digest preview could not be loaded.");
  }

  if (!data) return undefined;
  const row = data as DigestRow;
  return { digest: digestFromRow(row), status: row.status === "published" ? "published" : "draft" };
}

/** Role of the signed-in active member, or null. Never throws: used by the shared header. */
export async function getMemberRole(): Promise<"admin" | "reader" | null> {
  try {
    const client = await createServerSupabaseClient();
    const { data: claims } = await client.auth.getClaims();
    const userId = claims?.claims?.sub;
    if (!userId) return null;
    const { data } = await client
      .from("members")
      .select("role")
      .eq("user_id", userId)
      .eq("active", true)
      .maybeSingle();
    return data?.role === "admin" ? "admin" : data ? "reader" : null;
  } catch {
    return null;
  }
}
