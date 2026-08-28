import "server-only";

import { digestFromRow, type Digest, type DigestRow } from "@/lib/digests";
import { createServerSupabaseClient } from "@/lib/supabase-server";

const PUBLIC_FIELDS = "slug,published_on,title,summary,body";

export async function getPublishedDigests(): Promise<Digest[]> {
  const client = await createServerSupabaseClient();

  const { data, error } = await client
    .from("digests")
    .select(PUBLIC_FIELDS)
    .eq("status", "published")
    .order("published_on", { ascending: false });

  if (error) {
    console.error("Unable to load published digests:", error.message);
    return [];
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
    return undefined;
  }

  return data ? digestFromRow(data as DigestRow) : undefined;
}
