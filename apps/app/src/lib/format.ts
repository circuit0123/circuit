/** Short relative time: "now", "5m", "2h", "3d". */
export function ago(iso: string, now = Date.now()): string {
  const s = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (s < 60) return "now";
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

export function rupees(min?: number | null, max?: number | null): string | null {
  const f = (n: number) => (n >= 1000 ? `${Math.round(n / 1000)}k` : String(n));
  if (min && max && min !== max) return `₹${f(min)}–${f(max)}/mo`;
  const one = max ?? min;
  return one ? `₹${f(one)}/mo` : null;
}

const ROLES: Record<string, string> = {
  student: "Student", founder: "Founder", mentor: "Mentor", investor: "Investor", partner_admin: "Partner", super_admin: "Circuit team",
};
export const roleLabel = (r: string) => ROLES[r] ?? r;

const SECTORS: Record<string, string> = { d2c: "D2C", saas: "SaaS", deeptech: "Deep tech" };
/** "healthtech" → "Healthtech". The sector list is fixed; a few need their own spelling. */
export const sectorLabel = (s: string) => SECTORS[s.toLowerCase()] ?? (s ? s[0].toUpperCase() + s.slice(1).replace(/_/g, " ") : "");

const STAGES: Record<string, string> = { idea: "Idea stage", pre_seed: "Pre-seed", seed: "Seed", series_a_plus: "Series A+" };
export const stageLabel = (s: string) => STAGES[s] ?? s;

const KINDS: Record<string, string> = { internship: "Internship", full_time: "Full time", part_time: "Part time" };
export const kindLabel = (k: string) => KINDS[k] ?? k;

/** "3.2 km" under 10 km, "14 km" above. */
export const kmText = (km: number) => `${km < 10 ? km.toFixed(1) : Math.round(km)} km`;

/** A skill match in words (DESIGN.md §4: words, never a weak-looking number). Below 0.55 there is nothing to say. */
export function skillFit(score: number | null | undefined): string | null {
  if (score === null || score === undefined) return null;
  if (score >= 0.75) return "Strong skill match";
  if (score >= 0.55) return "Good skill match";
  return null;
}
