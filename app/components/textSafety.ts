// Mirrors normalizeEntry() in app/components/Leaderboard.tsx and the rules in
// COMMUNITY_DESIGN_SPEC.md section 7.1. Everything authored outside the
// codebase (feature-request titles/details, usernames, GitHub issue text) is
// untrusted and must be re-sanitized at the UI boundary even though the API
// also validates it server-side.
export const CONTROL_CHARACTERS = /[\u0000-\u001F\u007F-\u009F]/u;
const BIDI_FORMATTING = /[\u202A-\u202E\u2066-\u2069]/gu;
const ZERO_WIDTH = /[\u200B-\u200D\u2060\uFEFF]/gu;

export function stripInvisibleFormatting(value: string): string {
  return value.replace(BIDI_FORMATTING, "").replace(ZERO_WIDTH, "");
}

export function codePointSlice(value: string, maximum: number): string {
  return Array.from(value).slice(0, maximum).join("");
}

/** Truncates by code point, replacing the final visible character with `…`. */
export function displayText(value: string, maximum: number): string {
  const points = Array.from(value);
  return points.length > maximum ? `${points.slice(0, maximum - 1).join("")}…` : value;
}

/** Returns null when the untrusted string must not be rendered at all. */
export function safeDisplayText(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  if (trimmed.length === 0 || CONTROL_CHARACTERS.test(trimmed)) return null;
  return stripInvisibleFormatting(trimmed);
}

// Build-time constant, mirroring GITHUB_OWNER/GITHUB_REPO in
// server/alpha_poker_api/github.py. Nothing outside this repository is ever a
// valid destination for a rendered issue link.
export const GITHUB_REPO_URL = "https://github.com/sethusehitch/alpha-poker";

/** The one URL an issue row may link to, or null when the number is unusable. */
export function repoIssueUrl(issueNumber: unknown): string | null {
  if (typeof issueNumber !== "number" || !Number.isInteger(issueNumber) || issueNumber <= 0) return null;
  return `${GITHUB_REPO_URL}/issues/${issueNumber}`;
}

/**
 * Validates a server-supplied issue URL (spec 7.1.4). The check is exact
 * equality against the URL this repo would generate for that issue number, so
 * another owner/repo, a `/pull/` URL, a different issue number, a trailing
 * path, or a query string can never be rendered as an href.
 */
export function isRepoIssueUrl(value: unknown, issueNumber: unknown): boolean {
  const expected = repoIssueUrl(issueNumber);
  return expected !== null && typeof value === "string" && value === expected;
}
