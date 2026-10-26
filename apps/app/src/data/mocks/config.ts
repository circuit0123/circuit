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
  { id: "pulse_off", label: "Pulse off" },
  { id: "drop_off", label: "Daily Drop off" },
  { id: "home_off", label: "Pulse and Daily Drop off" },
  { id: "intros_used", label: "Intros used up" },
  { id: "requests", label: "Intros and requests waiting" },
  { id: "under18", label: "Under 18" },
  { id: "founder", label: "Founder" },
  { id: "discover_loading", label: "Discover loading" },
  { id: "discover_error", label: "Discover fails to load" },
  { id: "connect_loading", label: "Circuits and Inbox loading" },
  { id: "connect_error", label: "Circuits and Inbox fail to load" },
  { id: "send_fails", label: "Messages fail to send" },
  { id: "profile_empty", label: "Profile to fill in" },
  { id: "you_loading", label: "Profile, posts and Settings loading" },
  { id: "you_error", label: "Profile, posts and Settings fail to load" },
  { id: "upload_fails", label: "Uploads fail once" },
  { id: "export_ready", label: "Data export ready" },
  { id: "signup", label: "New member" },
  { id: "signup_ai_down", label: "New member, AI down" },
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

/**
 * "Replay onboarding": forgets the fake new member (the store in signup.ts, its saved colour, the cached first-paint colour) and reloads on
 * the New member scenario, so the next load starts at Welcome. The caller signs out first. Key names are the ones signup.ts and handlers.ts
 * use; the replay test in signup.spec.ts fails if they drift.
 */
export function restartSignup() {
  try {
    for (const k of ["circuit.mock.member", "circuit.mock.appearance", "circuit.appearance"]) localStorage.removeItem(k);
  } catch { /* nothing to forget */ }
  switchScenario("signup");
}

/** Switches scenario. A reload gives every hook a clean start, which is what a scenario means. */
export function switchScenario(id: Scenario) {
  resolved = id;
  try { localStorage.setItem(KEY, id); } catch { /* not remembered */ }
  const url = new URL(window.location.href);
  url.searchParams.delete("scenario");
  window.location.assign(url.toString());
}
