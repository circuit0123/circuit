import { AVATAR_TONES } from "./theme";

/** A deterministic "circuit board" pattern: orthogonal traces ending in nodes, drawn from a hash of an id (DESIGN.md §5 Imagery). */
export type Pattern = {
  bg: string;
  wide: string;
  line: string;
  /** Grid size the traces are drawn on: 32 x 32 for avatars, 96 x 72 for banners. */
  w: number;
  h: number;
  /** Polylines on that grid. */
  traces: string[];
  nodes: Array<{ x: number; y: number }>;
};

function hash(s: string): number {
  let h = 2166136261;
  for (const c of s) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return h >>> 0;
}

function prng(seed: number) {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const cache = new Map<string, Pattern>();

export function circuitPattern(id: string | number, banner = false): Pattern {
  const w = banner ? 96 : 32;
  const h = banner ? 72 : 32;
  const key = `${banner ? "b" : "a"}${id}`;
  const hit = cache.get(key);
  if (hit) return hit;
  const rnd = prng(hash(String(id)));
  const a = Math.floor(rnd() * AVATAR_TONES.length);
  const b = (a + 1 + Math.floor(rnd() * (AVATAR_TONES.length - 1))) % AVATAR_TONES.length;
  const traces: string[] = [];
  const nodes: Pattern["nodes"] = [];
  const count = banner ? 9 + Math.floor(rnd() * 5) : 3 + Math.floor(rnd() * 3);
  for (let t = 0; t < count; t++) {
    // Start on a grid line (multiples of 4) at an edge and walk 2-4 right-angle segments.
    let x = Math.floor(rnd() * (w / 4 - 1) + 1) * 4;
    let y = rnd() < 0.5 ? 0 : h;
    if (rnd() < 0.5) [x, y] = [Math.min(y, w), Math.min(x, h)];
    const pts = [[x, y]];
    let horizontal = rnd() < 0.5;
    const steps = 2 + Math.floor(rnd() * 3);
    for (let s = 0; s < steps; s++) {
      const len = (1 + Math.floor(rnd() * 4)) * 4 * (rnd() < 0.5 ? -1 : 1);
      if (horizontal) x = Math.max(0, Math.min(w, x + len));
      else y = Math.max(0, Math.min(h, y + len));
      pts.push([x, y]);
      horizontal = !horizontal;
    }
    traces.push(pts.map((p) => p.join(",")).join(" "));
    nodes.push({ x, y });
  }
  const p = { w, h, bg: AVATAR_TONES[a].bg, wide: AVATAR_TONES[b].bg, line: AVATAR_TONES[a].fg, traces, nodes };
  cache.set(key, p);
  return p;
}
