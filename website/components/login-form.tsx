"use client";

import { useState } from "react";
import { getBrowserSupabase } from "@/lib/supabase-browser";

export function LoginForm() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function signInWithGoogle() {
    const supabase = getBrowserSupabase();
    if (!supabase) {
      setError("Authentication is not configured.");
      return;
    }

    setBusy(true);
    setError("");
    const { error: signInError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        queryParams: {
          hd: "mellanni.com",
          prompt: "select_account",
        },
        redirectTo: `${window.location.origin}/auth/callback/?next=/`,
      },
    });

    if (signInError) {
      setError(signInError.message);
      setBusy(false);
    }
  }

  return (
    <div className="login-actions">
      <button className="primary-button google-login" type="button" onClick={signInWithGoogle} disabled={busy}>
        {busy ? "Opening Google…" : "Continue with Google"}
      </button>
      {error ? <p className="form-error" role="alert">{error}</p> : null}
    </div>
  );
}
