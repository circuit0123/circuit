/**
 * Mock mode for sign-up (scenarios "New member" and "New member, AI down"): a stateful fake of the endpoints and of Supabase sign-in, so
 * the whole of DESIGN.md §4 "Sign-up and onboarding" can be walked with no backend. State lives in localStorage so a reload resumes.
 * It mirrors the real rules (backend/apps/accounts/onboarding_state.py, apps/beta) closely enough that a screen that works here works there.
 * TEMPORARY like the other fixtures: replaced by the B7 contract fixtures.
 */
import { http, HttpResponse, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import { currentScenario } from "./config";
import { CONFIG, ME, dropOf } from "./fixtures";

export const isSignup = () => currentScenario() === "signup" || currentScenario() === "signup_ai_down";

/** The colleges the mock search knows. */
/** The cities the mock knows; the first is the pilot. */
const CITIES: ReadonlyArray<{ name: string; lat: number; lng: number }> = [
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

const ORGANISATIONS: readonly string[] = [
  "Sri Venkateswara Institute of Technology",
  "Thiagarajar College of Engineering",
  "PSG College of Technology",
  "Anna University, Guindy",
  "Loyola College",
  "SRM Institute of Science and Technology",
  "Madras Institute of Technology",
  "Government College of Technology, Coimbatore",
];

const KEY = "circuit.mock.member";
const API = "*/api";
const AUTH = "*/mock-supabase/auth/v1";
const POLICY = ME.policy_version;

type Store = {
  scenario: string;
  consent: boolean;
  beta: boolean;
  me: { name: string; role: string; city: string; college: string; bio: string; lat: number | null; lng: number | null; organisation_id: number | null; is_minor: boolean; profile_visibility: string; allow_requests: boolean };
  onboarding: { current_step: string | null; completed_at: string | null; answers: Record<string, Record<string, unknown>> };
  signup_source: string;
  offers: Schemas["NeedOfferOut"][];
  needs: Schemas["NeedOfferOut"][];
  waitlist: Array<{ email: string; role: string; src: string }>;
};

const fresh = (): Store => ({
  scenario: currentScenario(),
  consent: false,
  beta: false,
  me: { name: "", role: "student", city: "", college: "", bio: "", lat: null, lng: null, organisation_id: null, is_minor: false, profile_visibility: "members", allow_requests: true },
  onboarding: { current_step: null, completed_at: null, answers: {} },
  signup_source: "",
  offers: [],
  needs: [],
  waitlist: [],
});

function read(): Store {
  try {
    const s = JSON.parse(localStorage.getItem(KEY) ?? "null") as Store | null;
    if (s && s.scenario === currentScenario()) return s;
  } catch { /* start fresh */ }
  return fresh();
}
function write(s: Store) { try { localStorage.setItem(KEY, JSON.stringify(s)); } catch { /* not remembered */ } }
function update(f: (s: Store) => void): Store { const s = read(); f(s); write(s); return s; }

/** Test hook: `localStorage["circuit.mock.fail"] = "onboarding"` makes that call fail the way a dropped connection does. */
const failing = (what: string) => { try { return localStorage.getItem("circuit.mock.fail") === what; } catch { return false; } };

const error = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });

/* -- who am I ------------------------------------------------------------------------------------------------------ */

const APPEARANCE_KEY = "circuit.mock.appearance";
const appearance = (): Schemas["AppearanceOut"] => {
  try { return { ...ME.appearance, ...JSON.parse(localStorage.getItem(APPEARANCE_KEY) ?? "{}") }; } catch { return ME.appearance; }
};

export function signupMe(): Schemas["MeOut"] {
  const s = read();
  return {
    ...ME,
    id: 99,
    display_name: s.me.name,
    role: s.me.role as Schemas["MeOut"]["role"],
    bio: s.me.bio,
    city: s.me.city,
    college: s.me.college,
    lat: s.me.lat,
    lng: s.me.lng,
    organisation_id: s.me.organisation_id,
    is_minor: s.me.is_minor,
    profile_visibility: s.me.profile_visibility,
    allow_requests: s.me.allow_requests,
    beta_access: s.beta,
    needs_consent: !s.consent,
    appearance: appearance(),
  };
}
export const signupConfig = (): Schemas["ConfigOut"] => ({ ...CONFIG, beta_mode: true, beta_access: read().beta });

/* -- onboarding state (mirrors onboarding_state.py) ----------------------------------------------------------------- */

const STEPS = {
  default: ["invite", "name", "role", "age", "safety", "where", "work", "offers", "needs", "organisation", "photo", "colour", "ready"],
  investor: ["invite", "name", "role", "age", "where", "focus", "stage", "cheque", "verify", "photo", "colour", "ready"],
  partner: ["invite", "name", "role", "age", "where", "org_kind", "org", "org_verify", "goal", "photo", "colour", "ready"],
};
const ALL_STEPS = new Set([...STEPS.default, ...STEPS.investor, ...STEPS.partner]);

function onboardingOf(s: Store): Schemas["OnboardingOut"] {
  const choice = s.onboarding.answers.role?.choice;
  const branch = choice === "invest" ? "investor" : choice === "partner" ? "partner" : "default";
  const steps = STEPS[branch];
  const skip: string[] = [];
  if (s.beta) skip.push("invite");
  if (s.me.name) skip.push("name");
  if (s.me.city || s.me.lat !== null) skip.push("where");
  if (s.me.organisation_id) skip.push("organisation", "org");
  if (!s.me.is_minor) skip.push("safety");
  return {
    branch,
    steps,
    skip: steps.filter((x) => skip.includes(x)),
    current_step: s.onboarding.current_step,
    completed_at: s.onboarding.completed_at,
    answers: s.onboarding.answers,
    signup_source: s.signup_source,
  };
}

/* -- capabilities and the AI --------------------------------------------------------------------------------------- */

export const CAPABILITIES = [
  ["frontend-dev", "Frontend development", "Engineering"], ["backend-dev", "Backend development", "Engineering"], ["mobile-dev", "Mobile apps", "Engineering"],
  ["devops", "DevOps", "Engineering"], ["ml", "Machine learning", "Engineering"], ["data-analysis", "Data analysis", "Data"], ["data-viz", "Dashboards", "Data"],
  ["maps", "Maps", "Data"], ["ui-design", "UI design", "Design"], ["ux-research", "UX research", "Design"], ["video", "Video editing", "Design"],
  ["marketing", "Marketing", "Growth"], ["growth", "Growth", "Growth"], ["content", "Content writing", "Growth"], ["sales", "Sales", "Growth"],
  ["partnerships", "Partnerships", "Growth"], ["fundraising", "Fundraising", "Business"], ["finance", "Finance", "Business"], ["hiring", "Hiring", "Business"],
  ["operations", "Operations", "Business"], ["legal-regulatory", "Regulatory help", "Business"], ["product", "Product management", "Product"],
  ["pitching", "Pitching", "Product"], ["mentoring", "Mentoring", "People"],
].map(([slug, name, category]) => ({ slug, name, category })) satisfies Schemas["CapabilityOut"][];

export const TRAITS = [["builder", "Builder"], ["long-sales-cycle", "Long sales cycles"], ["technical-buyers", "Technical buyers"]].map(([slug, name]) => ({ slug, name })) satisfies Schemas["TraitOut"][];

const WORDS: Array<[RegExp, string]> = [
  [/react|frontend|front-end|interface/i, "frontend-dev"], [/backend|back-end|api|server/i, "backend-dev"], [/\bmaps?\b/i, "maps"], [/dashboard/i, "data-viz"],
  [/design|figma|ui\b/i, "ui-design"], [/data|analytics/i, "data-analysis"], [/market/i, "marketing"], [/sales|sell/i, "sales"], [/fundrais|investor/i, "fundraising"],
  [/hir(e|ing)|recruit/i, "hiring"], [/regulat|compliance/i, "legal-regulatory"], [/mentor/i, "mentoring"], [/machine learning|\bml\b/i, "ml"], [/video/i, "video"],
];

function extract(bio: string, aiDown: boolean): Schemas["ExtractOut"] {
  if (aiDown) return { source: "manual", suggestions: { needs: [], offers: [], skills: [], traits: [] } };
  const cut = bio.search(/looking for|need|want|help me/i);
  const found = (text: string) => [...new Set(WORDS.filter(([re]) => re.test(text)).map(([, slug]) => slug))];
  const offers = found(cut === -1 ? bio : bio.slice(0, cut)).slice(0, 8);
  const needs = cut === -1 ? [] : found(bio.slice(cut)).slice(0, 8);
  if (!offers.length && !needs.length) return { source: "manual", suggestions: { needs: [], offers: [], skills: [], traits: [] } };
  return { source: "llm", suggestions: { needs, offers, skills: offers, traits: ["builder"] } };
}

/* -- Supabase sign-in ----------------------------------------------------------------------------------------------- */

const now = () => Math.floor(Date.now() / 1000);
function session(email: string, provider: "email" | "google", name = "") {
  return {
    access_token: `mock-supabase-token:${email}`,
    token_type: "bearer",
    expires_in: 36_000,
    expires_at: now() + 36_000,
    refresh_token: "mock-refresh",
    user: {
      id: "00000000-0000-4000-8000-000000000099", aud: "authenticated", role: "authenticated", email,
      app_metadata: { provider }, user_metadata: name ? { full_name: name } : {}, created_at: new Date().toISOString(),
    },
  };
}
const emailOf = (request: Request) => decodeURIComponent((request.headers.get("authorization") ?? "").split(":")[1] ?? "");

/** What Google "returns" in mock mode. */
export const MOCK_GOOGLE = { email: "meera.krishnan@example.com", name: "Meera Krishnan" };

/** Codes: CIRCUIT-0001 lets anyone in; SVIT-2026 also joins the mock college; anything else is refused the way the real server refuses (one answer). */
const CODES: Record<string, number | null> = { "CIRCUIT-0001": null, "SVIT-2026": 7 };

export const signupHandlers: HttpHandler[] = [
  // Supabase (only the parts the app uses)
  http.post(`${AUTH}/otp`, () => HttpResponse.json({})),
  http.post(`${AUTH}/verify`, async ({ request }) => {
    const b = (await request.json()) as { email: string; token: string };
    if (b.token === "000000") return HttpResponse.json({ code: 403, error_code: "otp_expired", msg: "Token has expired or is invalid" }, { status: 403 });
    return HttpResponse.json(session(b.email, "email"));
  }),
  http.post(`${AUTH}/token`, async ({ request }) => {
    if (new URL(request.url).searchParams.get("grant_type") === "pkce") return HttpResponse.json(session(MOCK_GOOGLE.email, "google", MOCK_GOOGLE.name));
    return HttpResponse.json(session(MOCK_GOOGLE.email, "email"));
  }),
  http.get(`${AUTH}/user`, ({ request }) => HttpResponse.json(session(emailOf(request) || MOCK_GOOGLE.email, "email").user)),
  http.post(`${AUTH}/logout`, () => new HttpResponse(null, { status: 204 })),

  // The member
  http.post(`${API}/me/consent`, async ({ request }) => {
    if (!isSignup()) return;
    const b = (await request.json()) as { policy_version: string };
    if (b.policy_version !== POLICY) return error(422, "invalid_policy_version", "That isn't the current policy.");
    update((s) => { s.consent = true; });
    return HttpResponse.json({ policy_version: POLICY, accepted_at: new Date().toISOString() });
  }),
  http.post(`${API}/beta/redeem`, async ({ request }) => {
    if (!isSignup()) return;
    const code = ((await request.json()) as { code: string }).code.trim().toUpperCase();
    if (!read().beta && !(code in CODES)) return error(400, "invalid_code", "That code didn't work.");
    const org = CODES[code] ?? null;
    update((s) => {
      s.beta = true;
      if (org) { s.me.organisation_id = org; s.me.college ||= "Sri Venkateswara Institute of Technology"; }
    });
    return HttpResponse.json({ beta_access: true, organisation_id: org });
  }),
  http.post(`${API}/waitlist`, async ({ request }) => {
    if (!isSignup()) return;
    const b = (await request.json()) as { email: string; role: string; src: string };
    update((s) => { s.waitlist.push({ email: b.email, role: b.role, src: b.src }); });
    return HttpResponse.json({ status: "ok" }, { status: 202 });
  }),
  http.patch(`${API}/me`, async ({ request }) => {
    if (!isSignup()) return;
    const b = (await request.json()) as Record<string, unknown>;
    const allowed = ["bio", "city", "college", "display_name", "lat", "lng", "open_intro_slots", "role"];
    if (Object.keys(b).some((k) => !allowed.includes(k))) return error(422, "validation_error", "Unknown field.");
    if (b.role !== undefined && !["student", "founder", "mentor", "investor"].includes(b.role as string)) return error(422, "validation_error", "Unknown role.");
    update((s) => {
      if (typeof b.display_name === "string") s.me.name = b.display_name;
      if (typeof b.role === "string") s.me.role = b.role;
      if (typeof b.city === "string") s.me.city = b.city;
      if (typeof b.college === "string") s.me.college = b.college;
      if (typeof b.bio === "string") s.me.bio = b.bio;
      if (typeof b.lat === "number") s.me.lat = b.lat;
      if (typeof b.lng === "number") s.me.lng = b.lng;
    });
    return HttpResponse.json(signupMe());
  }),
  http.patch(`${API}/me/privacy`, async ({ request }) => {
    if (!isSignup()) return;
    const b = (await request.json()) as { profile_visibility?: string; allow_requests?: boolean };
    update((s) => {
      if (b.profile_visibility) s.me.profile_visibility = b.profile_visibility;
      if (typeof b.allow_requests === "boolean") s.me.allow_requests = b.allow_requests;
    });
    const m = signupMe();
    return HttpResponse.json({ profile_visibility: m.profile_visibility, visible_to_org: false, circuits_opt_in: false, allow_requests: m.allow_requests });
  }),
  http.get(`${API}/cities`, () => HttpResponse.json(CITIES.map((c, i) => ({ ...c, pilot: i === 0 }))),
  ),
  http.get(`${API}/organisations/search`, ({ request }) => {
    if (!isSignup()) return;
    const q = (new URL(request.url).searchParams.get("q") ?? "").toLowerCase();
    const hits = q.length < 2 ? [] : ORGANISATIONS.filter((o) => o.toLowerCase().includes(q)).slice(0, 10);
    return HttpResponse.json(hits.map((name, i) => ({ id: 100 + i, name, kind: "college", city: "Chennai" })));
  }),
  http.post(`${API}/organisations/join-by-email`, ({ request }) => {
    if (!isSignup()) return;
    if (!emailOf(request).endsWith("@svit.edu.in")) return error(404, "not_found", "No organisation uses that email domain.");
    update((s) => { s.me.organisation_id = 7; s.me.college ||= "Sri Venkateswara Institute of Technology"; });
    return HttpResponse.json({ id: 7, name: "Sri Venkateswara Institute of Technology", kind: "college", city: "Chennai" });
  }),

  // Onboarding
  http.get(`${API}/onboarding/state`, () => (isSignup() ? HttpResponse.json(onboardingOf(read())) : undefined)),
  http.patch(`${API}/onboarding/state`, async ({ request }) => {
    if (!isSignup()) return;
    if (failing("onboarding")) return HttpResponse.error();
    const b = (await request.json()) as { current_step?: string; answers?: Record<string, Record<string, unknown>>; signup_source?: string; completed?: boolean };
    const steps = [...Object.keys(b.answers ?? {}), ...(b.current_step ? [b.current_step] : [])];
    if (steps.some((x) => !ALL_STEPS.has(x))) return error(422, "validation_error", "Unknown step.");
    for (const [k, v] of Object.entries(b.answers ?? {})) if (JSON.stringify(v).length > 2000) return error(422, "answer_too_large", `The answer for ${k} is too long.`);
    const s = update((m) => {
      m.onboarding.answers = { ...m.onboarding.answers, ...(b.answers ?? {}) };
      if (b.current_step) m.onboarding.current_step = b.current_step;
      if (b.completed && !m.onboarding.completed_at) m.onboarding.completed_at = new Date().toISOString();
      if (b.signup_source && !m.signup_source) m.signup_source = b.signup_source;
    });
    return HttpResponse.json(onboardingOf(s));
  }),
  http.post(`${API}/onboarding/extract`, async ({ request }) => {
    if (!isSignup()) return;
    const { bio } = (await request.json()) as { bio: string };
    return HttpResponse.json(extract(bio, currentScenario() === "signup_ai_down"));
  }),
  http.get(`${API}/capabilities`, () => HttpResponse.json(CAPABILITIES)),
  http.get(`${API}/traits`, () => HttpResponse.json(TRAITS)),
  http.put(`${API}/me/offers`, async ({ request }) => {
    const body = (await request.json()) as Schemas["NeedOfferIn"][];
    const out = body.map((x) => ({ capability: x.capability, description: x.description ?? "" }));
    if (isSignup()) update((s) => { s.offers = out; });
    return HttpResponse.json(out);
  }),
  http.put(`${API}/me/needs`, async ({ request }) => {
    const body = (await request.json()) as Schemas["NeedOfferIn"][];
    const out = body.map((x) => ({ capability: x.capability, description: x.description ?? "" }));
    if (isSignup()) update((s) => { s.needs = out; });
    return HttpResponse.json(out);
  }),
  http.put(`${API}/me/skills`, async ({ request }) => HttpResponse.json(((await request.json()) as Schemas["SkillIn"][]).map((x) => ({ capability: x.capability, level: x.level ?? 1, proof_url: x.proof_url ?? "" })))),
  http.put(`${API}/me/traits`, async ({ request }) => HttpResponse.json(await request.json())),

  // Test hook: `localStorage["circuit.mock.empty"] = "drop"` means no drop has been built for this member yet (the Ready screen's "tomorrow" path).
  http.get(`${API}/drop/today`, () => {
    if (!isSignup()) return;
    try { if (localStorage.getItem("circuit.mock.empty") === "drop") return HttpResponse.json(dropOf([])); } catch { /* the normal drop */ }
  }),

  // Test hook: lets Playwright read what the "server" holds (never called by the app).
  http.get("*/mock-supabase/_state", () => HttpResponse.json(read())),
];
