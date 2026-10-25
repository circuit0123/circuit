/** Build-time public settings (PRODUCTION.md §2a). Nothing here is a secret; nothing is hard-coded. */
const trim = (v: string | undefined) => (v ?? "").replace(/\/+$/, "");

export const APP_URL = trim(process.env.NEXT_PUBLIC_APP_URL);
export const LANDING_URL = trim(process.env.NEXT_PUBLIC_LANDING_URL);
export const API_URL = trim(process.env.NEXT_PUBLIC_API_URL);
/** Footer "Contact" link. Left out when not set. */
export const CONTACT_EMAIL = process.env.NEXT_PUBLIC_CONTACT_EMAIL ?? "";
/** Footer company name. Left out when not set (never a [placeholder]). */
export const COMPANY_LEGAL_NAME = process.env.NEXT_PUBLIC_COMPANY_LEGAL_NAME ?? "";

export type Role = "student" | "founder" | "mentor" | "investor" | "partner";

/** A `src` label: lower-case letters, digits, `-` and `_`, up to 40 (the same rule as the API and the app). Anything else is ignored. */
export const isSrc = (v: string | null | undefined): v is string => !!v && /^[a-z0-9_-]{1,40}$/.test(v);

/** Where every call to action goes: the app's join screen with the role and the page it came from. The hero passes no role. */
export function joinUrl(src: string, role?: Role): string {
  const q = new URLSearchParams();
  if (role) q.set("role", role);
  q.set("src", src);
  return `${APP_URL}/join?${q.toString()}`;
}
