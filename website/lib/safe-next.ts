/** Same-origin path to return to after sign-in. Anything else falls back to home. */
export function safeNextPath(value: string | null | undefined) {
  return value?.startsWith("/")
    && !value.startsWith("//")
    && !value.includes("\\")
    ? value
    : "/";
}
