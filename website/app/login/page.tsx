import type { Metadata } from "next";
import { LoginForm } from "@/components/login-form";

export const metadata: Metadata = {
  title: "Sign in",
  description: "Sign in to Mellanni Marketing Intelligence.",
};

type LoginPageProps = {
  searchParams: Promise<{ error?: string }>;
};

const messages: Record<string, string> = {
  access_denied: "This Google account does not have active Mellanni access.",
  auth_callback: "Google sign-in could not be completed. Try again.",
  configuration: "Authentication is not configured. Contact the site administrator.",
};

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const { error } = await searchParams;

  return (
    <div className="shell login-page">
      <section className="login-panel" aria-labelledby="login-title">
        <p className="eyebrow">Private company workspace</p>
        <h1 id="login-title">Marketing intelligence for Mellanni.</h1>
        <p>
          Use your company Google account. Access is limited to active personal addresses ending in <strong>@mellanni.com</strong>.
        </p>
        {error ? <p className="form-error" role="alert">{messages[error] ?? messages.auth_callback}</p> : null}
        <LoginForm />
      </section>
    </div>
  );
}
