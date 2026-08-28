import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { usedOAuth } from "@/lib/auth-claims";

const PUBLIC_PATHS = new Set(["/login", "/auth/callback"]);

function normalizedPath(pathname: string) {
  return pathname.replace(/\/+$/, "") || "/";
}

function copyCookies(source: NextResponse, destination: NextResponse) {
  source.cookies.getAll().forEach((cookie) => destination.cookies.set(cookie));
  return destination;
}

function redirect(request: NextRequest, response: NextResponse, pathname: string) {
  return copyCookies(response, NextResponse.redirect(new URL(pathname, request.url)));
}

export async function updateSession(request: NextRequest) {
  const path = normalizedPath(request.nextUrl.pathname);
  const isPublic = PUBLIC_PATHS.has(path);
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (!url || !key) {
    if (path === "/login") return NextResponse.next({ request });
    return NextResponse.redirect(new URL("/login/?error=configuration", request.url));
  }

  let response = NextResponse.next({ request });
  const supabase = createServerClient(url, key, {
    cookies: {
      getAll: () => request.cookies.getAll(),
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
        response = NextResponse.next({ request });
        cookiesToSet.forEach(({ name, options, value }) => {
          response.cookies.set(name, value, options);
        });
      },
    },
  });

  if (path === "/auth/callback") return response;

  const { data, error } = await supabase.auth.getClaims();
  const userId = !error && usedOAuth(data?.claims?.amr)
    ? data?.claims?.sub
    : undefined;

  if (!userId) {
    return isPublic ? response : redirect(request, response, "/login/");
  }

  const { data: member } = await supabase
    .from("members")
    .select("role")
    .eq("user_id", userId)
    .eq("active", true)
    .maybeSingle();

  if (!member) {
    return path === "/login"
      ? response
      : redirect(request, response, "/login/?error=access_denied");
  }

  if (path === "/login") return redirect(request, response, "/");
  if ((path === "/admin" || path.startsWith("/admin/")) && member.role !== "admin") {
    return redirect(request, response, "/");
  }

  return response;
}
