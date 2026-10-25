import { API_URL } from "./env";

export type Features = Readonly<Record<string, boolean>>;

/** Everything off: what the pages assume when the API can't be asked. Off is the safe side (waitlist forms instead of app links). */
const ALL_OFF: Features = {};

const isFeatures = (v: unknown): v is Record<string, boolean> =>
  typeof v === "object" && v !== null && Object.values(v).every((x) => typeof x === "boolean");

async function load(): Promise<Features> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 2; attempt++) {
    try {
      const res = await fetch(`${API_URL}/api/config`, { signal: AbortSignal.timeout(3000) });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body: unknown = await res.json();
      const features = (body as { features?: unknown } | null)?.features;
      if (!isFeatures(features)) throw new Error("unexpected /api/config shape");
      return features;
    } catch (e) {
      lastError = e;
    }
  }
  console.warn(`[landing] Could not read ${API_URL}/api/config at build time (${String(lastError)}). Treating every feature as off.`);
  return ALL_OFF;
}

let memo: Promise<Features> | undefined;

/**
 * The feature flags for anonymous visitors, read from `GET /api/config` once per build (DESIGN.md §3). Server components only.
 * Flags are baked into the static pages, so changing one in admin needs a landing redeploy (RUNBOOK.md).
 * Any failure (timeout, bad response) → every flag off, with a warning in the build log.
 */
export function getFeatures(): Promise<Features> {
  memo ??= load();
  return memo;
}

export const flagOn = (features: Features, name: "investor_mode" | "partner_mode") => features[name] === true;
