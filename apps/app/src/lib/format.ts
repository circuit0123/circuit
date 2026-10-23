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
