export function usedOAuth(amr: unknown) {
  return Array.isArray(amr)
    && amr.some((entry) => (
      typeof entry === "object"
      && entry !== null
      && "method" in entry
      && entry.method === "oauth"
    ));
}
