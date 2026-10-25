import { APP_ENV } from "@/lib/env";

/** Mock mode (`make mock`): the app runs against Mock Service Worker handlers, with no backend and no login. Only honoured in the dev environment. */
export const MOCK = process.env.NEXT_PUBLIC_MOCK === "1" && APP_ENV === "dev";

export const SCENARIOS = [
  { id: "default", label: "Default" },
  { id: "empty", label: "Empty" },
  { id: "loading", label: "Loading" },
  { id: "error", label: "Error" },
  { id: "slow3g", label: "Slow 3G" },
  { id: "beta", label: "Beta access missing" },
  { id: "features_off", label: "Features off" },
  { id: "under18", label: "Under 18" },
] as const;

export type Scenario = (typeof SCENARIOS)[number]["id"];
const KEY = "circuit.mock.scenario";
const isScenario = (s: string | null): s is Scenario => SCENARIOS.some((x) => x.id === s);

let resolved: Scenario | null = null;

/**
 * The scenario in use: `?scenario=` in the address wins and is remembered; otherwise the remembered one; otherwise default.
 * Decided once per page load, so a render in the middle of switching can't write the old choice back.
 */
export function currentScenario(): Scenario {
  if (typeof window === "undefined") return "default";
  if (resolved) return resolved;
  const asked = new URLSearchParams(window.location.search).get("scenario");
  let pick: Scenario = "default";
  try {
    const saved = localStorage.getItem(KEY);
    pick = isScenario(asked) ? asked : isScenario(saved) ? saved : "default";
    localStorage.setItem(KEY, pick);
  } catch {
    if (isScenario(asked)) pick = asked;
  }
  resolved = pick;
  return pick;
}

/** Switches scenario. A reload gives every hook a clean start, which is what a scenario means. */
export function switchScenario(id: Scenario) {
  resolved = id;
  try { localStorage.setItem(KEY, id); } catch { /* not remembered */ }
  const url = new URL(window.location.href);
  url.searchParams.delete("scenario");
  window.location.assign(url.toString());
}
