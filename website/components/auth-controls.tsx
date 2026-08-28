"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { getBrowserSupabase } from "@/lib/supabase-browser";

export function AuthControls() {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = getBrowserSupabase();
  const [email, setEmail] = useState<string>();

  useEffect(() => {
    if (!supabase) return;

    void supabase.auth.getSession().then(({ data }) => {
      setEmail(data.session?.user.email);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, session) => {
      setEmail(session?.user.email);
    });
    return () => data.subscription.unsubscribe();
  }, [supabase]);

  if (!supabase || !email || pathname.replace(/\/+$/, "") === "/login") return null;

  async function signOut() {
    await supabase?.auth.signOut();
    router.replace("/login/");
    router.refresh();
  }

  return (
    <div className="auth-controls">
      <span>{email}</span>
      <button className="text-button" type="button" onClick={signOut}>Sign out</button>
    </div>
  );
}
