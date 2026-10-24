/** Motion constants from DESIGN.md §7. */
export const spring = { type: "spring", duration: 0.35, bounce: 0 } as const;
export const sheetSpring = { type: "spring", duration: 0.45, bounce: 0.1 } as const;
export const pushSpring = { type: "spring", duration: 0.4, bounce: 0 } as const;
export const fade = { duration: 0.15 } as const;

/** Eight muted tones for avatars without a photo (DESIGN.md §5 Imagery). Text on each is AA. */
export const AVATAR_TONES = [
  { bg: "#3b4a6b", fg: "#f1f3fa" },
  { bg: "#4a5d4f", fg: "#f0f5f1" },
  { bg: "#6b4a4a", fg: "#faf1f1" },
  { bg: "#5d4a6b", fg: "#f6f1fa" },
  { bg: "#6b5d3b", fg: "#faf6ec" },
  { bg: "#3b6b66", fg: "#eefaf8" },
  { bg: "#6b3b57", fg: "#faeff5" },
  { bg: "#4d5560", fg: "#f2f4f7" },
] as const;

export function initials(name: string): string {
  const words = name
    .replace(/^(dr|mr|ms|mrs|prof)\.?\s+/i, "")
    .split(/\s+/)
    .filter(Boolean);
  if (words.length === 0) return "?";
  const first = words[0][0] ?? "";
  const last = words.length > 1 ? (words[words.length - 1][0] ?? "") : "";
  return (first + last).toUpperCase();
}

export function toneFor(name: string) {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return AVATAR_TONES[h % AVATAR_TONES.length];
}
