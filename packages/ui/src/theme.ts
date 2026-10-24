/** Motion constants from DESIGN.md §7. */
export const spring = { type: "spring", duration: 0.35, bounce: 0 } as const;
export const sheetSpring = { type: "spring", duration: 0.45, bounce: 0.1 } as const;
export const pushSpring = { type: "spring", duration: 0.4, bounce: 0 } as const;
export const fade = { duration: 0.15 } as const;

/** Placeholder art is grey (DESIGN.md §5 Media): the existing surface tokens with text-subtle traces, so it follows the theme. */
export const AVATAR_TONES = [
  { bg: "var(--surface-2)", wide: "var(--surface-3)", fg: "var(--text-subtle)" },
  { bg: "var(--surface-3)", wide: "var(--surface-2)", fg: "var(--text-subtle)" },
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
