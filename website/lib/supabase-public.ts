import "server-only";

import { createClient } from "@supabase/supabase-js";
import {
  digestFromRow,
  sampleDigest,
  type Digest,
  type DigestRow,
} from "@/lib/digests";

const PUBLIC_FIELDS = "slug,published_on,title,summary,body";

function publicClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;

  return createClient(url, key, {
    auth: {
      autoRefreshToken: false,
      detectSessionInUrl: false,
      persistSession: false,
    },
  });
}

export async function getPublishedDigests(): Promise<Digest[]> {
  const client = publicClient();
  if (!client) return [sampleDigest];

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
  const client = publicClient();
  if (!client) return slug === sampleDigest.slug ? sampleDigest : undefined;

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
