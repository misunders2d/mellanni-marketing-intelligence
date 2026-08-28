import { NextResponse } from "next/server";
import { usedOAuth } from "@/lib/auth-claims";
import { createServerSupabaseClient } from "@/lib/supabase-server";

function safeNext(value: string | null) {
  return value?.startsWith("/")
    && !value.startsWith("//")
    && !value.includes("\\")
    ? value
    : "/";
}

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const code = requestUrl.searchParams.get("code");

  if (!code) {
    return NextResponse.redirect(new URL("/login/?error=auth_callback", requestUrl.origin));
  }

  const supabase = await createServerSupabaseClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);
  if (error) {
    return NextResponse.redirect(new URL("/login/?error=auth_callback", requestUrl.origin));
  }

  const { data: claims } = await supabase.auth.getClaims();
  const userId = usedOAuth(claims?.claims?.amr) ? claims?.claims?.sub : undefined;
  const { data: member } = userId
    ? await supabase
        .from("members")
        .select("user_id")
        .eq("user_id", userId)
        .eq("active", true)
        .maybeSingle()
    : { data: null };

  if (!member) {
    await supabase.auth.signOut();
    return NextResponse.redirect(new URL("/login/?error=access_denied", requestUrl.origin));
  }

  return NextResponse.redirect(new URL(safeNext(requestUrl.searchParams.get("next")), requestUrl.origin));
}
