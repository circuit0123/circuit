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

/**
 * API needed: Pulse items for partner calls/events and for promoted roles. `GET /api/pulse` returns neither today, so these two
 * stand-ins exist for mock mode only (never in a real build, where a flag on with no item simply draws nothing). Marked, and listed in
 * PROGRESS.md under "Frontend → API needed". Replace with real Pulse items and a "hide promotion" call.
 */
export const PROMOTED_STAND_IN: { key: string; startup: string; why: string; role: RoleView; /** Under-18 members only see promotions from verified startups. */ verified: boolean } = {
  key: "promoted-stand-in",
  startup: "Sutragrid",
  verified: false,
  why: "Promoted to people in Chennai interested in frontend development.",
  role: { id: 304, title: "Backend engineer intern", startup: "Sutragrid", place: "Ambattur, Chennai", km: 14, stipend: "₹15k–18k/mo", match: 78, tags: ["Backend"] },
};
export const PARTNER_STAND_IN = {
  key: "partner-stand-in",
  org: "SVIT Incubation Cell",
  text: "Demo day on 14 November. Eight student teams show what they built this term. Anyone can come.",
} as const;

/**
 * API needed (F4): whether a role's startup is verified (claimed through its company email domain). Under-18 members only see roles and
 * promotions from verified startups, and `JobOut` doesn't say. Until it does, a role without this field counts as unverified, so
 * under-18 members see no roles at all in a real build (the safe side). Mock fixtures carry it.
 */
export type MissingJobFields = { startup_verified?: boolean };

/** API needed (F4): a promoted startup for the one slot at the top of Discover → Startups. Mock mode only, like PROMOTED_STAND_IN. */
export const PROMOTED_STARTUP_STAND_IN = {
  key: "promoted-startup-stand-in",
  id: 42,
  name: "Tatvagrid",
  sector: "agritech",
  verified: true,
  why: "Promoted to people in Chennai interested in mobile apps.",
} as const;

export type StartupFounder = { id: number; name: string; role: string; level: number };
export type StartupLog = { id: number; src: string; alt: string };

/** A believable screenshot for a build log tile (DESIGN.md §5 Imagery): a title and three rows of real-looking data. */
function screen(title: string, rows: Array<[string, string]>) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="480" height="480" viewBox="0 0 480 480" font-family="Arial, sans-serif"><rect width="480" height="480" fill="#0b1f18"/><text x="28" y="72" font-size="24" font-weight="700" fill="#f3eef5">${title}</text>${rows.map((r, i) => `<g transform="translate(28 ${120 + i * 92})"><rect width="424" height="72" rx="12" fill="#142c23"/><text x="18" y="44" font-size="20" fill="#f3eef5">${r[0]}</text><text x="300" y="44" font-size="20" fill="#2fbf8a">${r[1]}</text></g>`).join("")}</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}

/**
 * API needed (F4): the Startup page's team size, founders and build logs. `StartupOut` has none of them, so mock mode reads this marked
 * stand-in and a real build leaves those parts out until the API sends them.
 */
export const STARTUP_EXTRAS: Record<number, { teamSize: number; founders: StartupFounder[]; logs: StartupLog[] }> = {
  41: {
    teamSize: 6,
    founders: [{ id: 4, name: "Arjun Mehta", role: "Founder", level: 3 }, { id: 3, name: "Priya Nair", role: "Co-founder", level: 2 }],
    logs: [
      { id: 101, src: screen("Stock today · Adyar", [["Paracetamol 500 mg", "1,240"], ["ORS sachets", "860"], ["Gloves (M)", "412"]]), alt: "Stock screen listing three medicines and units in stock" },
      { id: 111, src: screen("Reorder by Friday", [["Thermometers", "₹28,500"], ["Gloves (M)", "₹24,720"], ["ORS sachets", "₹10,320"]]), alt: "Reorder list with three items and their value in rupees" },
      { id: 112, src: screen("Pharmacies live", [["Adyar", "14"], ["Velachery", "9"], ["Besant Nagar", "5"]]), alt: "Count of pharmacies using the app in three neighbourhoods" },
    ],
  },
  42: {
    teamSize: 4,
    founders: [{ id: 8, name: "Divya Menon", role: "Founder", level: 2 }],
    logs: [{ id: 121, src: screen("Today's soil reading", [["Moisture", "31%"], ["Nitrogen", "Low"], ["Next watering", "Thu"]]), alt: "One farm's soil reading with moisture, nitrogen and the next watering day" }],
  },
};

/* -- F6: profiles, posting, settings -------------------------------------------------------------------------------- */

export type Highlight = { id: number; title: string; src: string; alt: string };
export type Connection = "none" | "pending" | "incoming" | "connected";

/**
 * API needed (F6): what a profile page shows that `ProfileOut` and `MeOut` don't carry. A headline, organisation, whether the person is
 * under 18 and hidden, whether you are connected, the mutual-connection count, whether you may message them, pinned highlights, and the
 * circuits you closed with them. Mock mode reads this marked stand-in; a real build leaves those parts out (no highlights, no circuits
 * tab, no mutual count) and lets the server refuse what isn't allowed.
 */
export type ProfileExtras = {
  headline?: string;
  org?: string;
  minor?: boolean;
  /** Under-18 profiles are hidden from people who aren't connected (DESIGN.md §8). */
  hidden?: boolean;
  connection?: Connection;
  mutuals?: number;
  /** Strangers can't message under-18s or people who turned requests off. */
  canMessage?: boolean;
  highlights?: Highlight[];
  circuits?: string[];
};

export const PROFILE_EXTRAS: Record<number, ProfileExtras> = {
  1: {
    headline: "Frontend developer",
    org: "Sri Venkateswara Institute of Technology",
    highlights: [
      { id: 1, title: "Farm map v2", src: screen("Farm map · Thiruvallur", [["Plots mapped", "126"], ["Wells", "18"], ["Soil tests", "41"]]), alt: "Farm map summary with plots, wells and soil tests counted" },
      { id: 2, title: "Soil dashboard", src: screen("Soil this week", [["Moisture", "31%"], ["Nitrogen", "Low"], ["pH", "6.8"]]), alt: "Soil dashboard with moisture, nitrogen and pH" },
    ],
    circuits: ["Completed circuit, September 2026"],
  },
  2: { headline: "Building a Kannada voice assistant", connection: "none", mutuals: 4, canMessage: true, circuits: ["Completed circuit, August 2026"],
    highlights: [{ id: 21, title: "Voice demo", src: screen("Kannada voice · test run", [["Words understood", "92%"], ["Speakers", "40"], ["Dialects", "3"]]), alt: "Test run summary for a Kannada voice assistant" }] },
  3: { headline: "Running a lab-diagnostics startup", connection: "pending", mutuals: 2, canMessage: true },
  4: { headline: "Hiring for an inventory platform", connection: "connected", mutuals: 9, canMessage: true, circuits: ["Completed circuit, September 2026"] },
  5: { headline: "Biotech founder, assay kits", connection: "none", mutuals: 0, canMessage: true },
  7: { headline: "Ex-VP sales, deep tech", connection: "connected", mutuals: 12, canMessage: true },
  11: { headline: "Class 11, school robotics club", minor: true, hidden: true, connection: "none", mutuals: 1, canMessage: false },
  21: { headline: "Ex-founder, offline-first apps", connection: "connected", mutuals: 12, canMessage: true },
};

/**
 * API needed (F6): an `organisation_name` and a `headline` on `MeOut`. The own profile and its strength meter read this marked stand-in in
 * mock mode; a real build shows the city and role line only and leaves the headline step out of the meter.
 */
export const ME_EXTRAS = PROFILE_EXTRAS[1];
