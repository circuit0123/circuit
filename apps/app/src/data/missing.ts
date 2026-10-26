import type { RoleView } from "@circuit/ui";

/**
 * Data the screens need that the API does not give yet. Never an invented endpoint: these are marked stand-ins, listed in PROGRESS.md
 * under "Frontend → API needed", and replaced when the endpoint exists.
 */

/** API needed: a city list with centres (sign-up step 7 "Choose a city", and naming the city from "Use my location"). The pilot city is first. */
export const CITIES: ReadonlyArray<{ name: string; lat: number; lng: number }> = [
  { name: "Chennai", lat: 13.08, lng: 80.27 },
  { name: "Madurai", lat: 9.93, lng: 78.12 },
  { name: "Coimbatore", lat: 11.02, lng: 76.96 },
  { name: "Bengaluru", lat: 12.97, lng: 77.59 },
  { name: "Hyderabad", lat: 17.39, lng: 78.49 },
  { name: "Kochi", lat: 9.93, lng: 76.27 },
  { name: "Mumbai", lat: 19.08, lng: 72.88 },
  { name: "Pune", lat: 18.52, lng: 73.86 },
  { name: "Delhi", lat: 28.61, lng: 77.21 },
  { name: "Kolkata", lat: 22.57, lng: 88.36 },
];

/** API needed: organisation search (sign-up step 11). Mock mode only; real builds search nothing and accept the typed name. */
export const ORGANISATIONS: readonly string[] = [
  "Sri Venkateswara Institute of Technology",
  "Thiagarajar College of Engineering",
  "PSG College of Technology",
  "Anna University, Guindy",
  "Loyola College",
  "SRM Institute of Science and Technology",
  "Madras Institute of Technology",
  "Government College of Technology, Coimbatore",
];

/**
 * API needed: Pulse items for partner calls/events and for promoted roles. `GET /api/pulse` returns neither today, so these two
 * stand-ins exist for mock mode only (never in a real build, where a flag on with no item simply draws nothing). Marked, and listed in
 * PROGRESS.md under "Frontend → API needed". Replace with real Pulse items and a "hide promotion" call.
 */
export const PROMOTED_STAND_IN: { key: string; startup: string; why: string; role: RoleView } = {
  key: "promoted-stand-in",
  startup: "Sutragrid",
  why: "Promoted to people in Chennai interested in frontend development.",
  role: { id: 302, title: "Backend engineer intern", startup: "Sutragrid", place: "Guindy, Chennai", km: 5.8, stipend: "₹15k/mo", match: 78, tags: ["Backend"] },
};
export const PARTNER_STAND_IN = {
  key: "partner-stand-in",
  org: "SVIT Incubation Cell",
  text: "Demo day on 14 November. Eight student teams show what they built this term. Anyone can come.",
} as const;
