const PROBE_ORIGIN = "http://same-origin.invalid";
// URL parsers silently drop tab/newline, so "/\t/evil.com" would become "//evil.com".
const CONTROL_CHARACTERS = /[\u0000-\u001f\u007f]/;

/** Same-origin path to return to after sign-in. Anything else falls back to home. */
export function safeNextPath(value: string | null | undefined) {
  if (!value?.startsWith("/") || value.startsWith("//") || value.includes("\\") || CONTROL_CHARACTERS.test(value)) {
    return "/";
  }
  try {
    const url = new URL(value, PROBE_ORIGIN);
    // Dot segments can normalize "/.//evil.com" into the protocol-relative "//evil.com".
    const path = url.pathname + url.search + url.hash;
    return url.origin === PROBE_ORIGIN && !path.startsWith("//") ? path : "/";
  } catch {
    return "/";
  }
}
