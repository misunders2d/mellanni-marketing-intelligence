"use client";

import { useEffect } from "react";

export default function ErrorPage({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <section className="shell not-found" role="alert">
      <p className="eyebrow">Archive unavailable</p>
      <h1>The digest archive could not be loaded.</h1>
      <p>
        This is a temporary database or network problem, not an empty archive. Try again in a moment; if it persists, tell the site administrator.
      </p>
      <button className="primary-button" type="button" onClick={reset}>Try again</button>
    </section>
  );
}
