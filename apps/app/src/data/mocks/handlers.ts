import { delay, http, HttpResponse, type HttpHandler, type HttpResponseResolver } from "msw";
import type { Schemas } from "@circuit/api-client";
import { currentScenario, type Scenario } from "./config";
import { isSignup, signupConfig, signupHandlers, signupMe } from "./signup";
import { circuitHandlers } from "./circuits";
import { discoverHandlers } from "./discover";
import { inboxHandlers } from "./inbox";
import { postHandlers } from "./posts";
import { requestHandlers } from "./requests";
import { SHORT_BIO, mePatch, profileFirstHandlers, profileHandlers } from "./profile";
import { privacyFor, settingsHandlers } from "./settings";
import { CONFIG, DROP_CARDS, INTRO, LIVEWIRE, MATCHES, ME, NOTIFICATIONS, ONBOARDING, PEOPLE, PERSONAS, PULSE, dropOf } from "./fixtures";

/**
 * Mock Service Worker handlers for every endpoint the data hooks call today. A call to anything else answers 404 in the standard
 * error format and logs a warning, so a hook that starts using a new endpoint shows up here at once.
 * TEMPORARY: replaced by handlers generated from the B7 contract fixtures.
 */
const API = "*/api";
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });

const APPEARANCE_KEY = "circuit.mock.appearance";
const readAppearance = (): Schemas["AppearanceOut"] => {
  try { return { ...ME.appearance, ...JSON.parse(localStorage.getItem(APPEARANCE_KEY) ?? "{}") }; } catch { return ME.appearance; }
};

/** Swipes made in this page load: the Daily Drop remembers what you answered. */
const answered = new Map<number, "intro" | "skip">();

function me(s: Scenario): Schemas["MeOut"] {
  if (isSignup()) return signupMe();
  // Privacy and Edit profile changes (F6) show up here too, as they would from the real /api/me.
  const base = { ...ME, appearance: readAppearance(), ...privacyFor(s), ...(s === "profile_empty" || s === "empty" ? { bio: SHORT_BIO } : {}), ...mePatch };
  if (s === "beta") return { ...base, beta_access: false };
  if (s === "founder") return { ...base, id: PEOPLE.priya.id, display_name: PEOPLE.priya.display_name, role: "founder", bio: "Co-founder of Aravind Pathology. Stock software for pharmacies." };
  if (s === "under18") return { ...base, is_minor: true, bio: "Class 12 student. I build small apps for my school robotics club.", ...mePatch };
  return base;
}

function config(s: Scenario): Schemas["ConfigOut"] {
  if (isSignup()) return signupConfig();
  if (s === "beta") return { ...CONFIG, beta_mode: true, beta_access: false };
  // With Pulse off, what depends on it (promotions, then payments) is off too: the server refuses a flag on without its dependency.
  const off = (...names: string[]) => ({ ...CONFIG, features: { ...CONFIG.features, ...Object.fromEntries(names.map((n) => [n, false])) } });
  if (s === "pulse_off") return off("pulse", "promotions", "payments");
  if (s === "drop_off") return off("daily_drop");
  if (s === "home_off") return off("pulse", "promotions", "payments", "daily_drop");
  if (s === "features_off") return { ...CONFIG, features: Object.fromEntries(Object.keys(CONFIG.features).map((k) => [k, false])) };
  return CONFIG;
}

const person = (id: number): Schemas["PersonOut"] => {
  const p = Object.values(PEOPLE).find((x) => x.id === id) ?? PEOPLE.asha;
  return { id: p.id, display_name: p.display_name, role: p.role, verification_level: p.verification_level };
};
/** Mock people for the intro flow: Kavya (5) shares no connection with Ravi, Arjun (4) is already connected and has no slots left this week, everyone else is reached via Dr. Lakshmi. */
const NO_PATH = 5;
const CONNECTED = 4;
const FULL = 4;

/** Notifications read in this page load. */
const readIds = new Set<number>();
const notifications = (s: Scenario) => (s === "empty" ? [] : NOTIFICATIONS.map((n) => ({ ...n, read: n.read || readIds.has(n.id) })));

const noDrop = (s: Scenario) => s === "empty" || s === "under18";

type Info = Parameters<HttpResponseResolver>[0];

/** Wraps a resolver with the scenario's behaviour: wait (loading, slow 3G) or fail (error). */
function scenario(fn: (s: Scenario, info: Info) => Response | Promise<Response>) {
  return async (info: Info): Promise<Response> => {
    const s = currentScenario();
    if (s === "loading") await delay("infinite");
    if (s === "slow3g") await delay(2000);
    if (s === "error") return envelope(500, "internal_error", "Something went wrong on our side.");
    return fn(s, info);
  };
}

export const handlers: HttpHandler[] = [
  ...requestHandlers, // intros and connection requests to answer (the `requests` scenario has some)
  ...profileFirstHandlers, // your needs, offers and skills; they step aside in the New member scenarios
  ...signupHandlers, // each answers only in the New member scenarios and otherwise lets the handlers below take over
  http.get(`${API}/config`, scenario((s) => HttpResponse.json(config(s)))),
  http.get(`${API}/me`, scenario((s) => HttpResponse.json(me(s)))),
  http.patch(`${API}/me/appearance`, scenario(async (_s, { request }) => {
    const next = { ...readAppearance(), ...Object.fromEntries(Object.entries((await request.json()) as object).filter(([, v]) => v !== undefined && v !== null)) };
    try { localStorage.setItem(APPEARANCE_KEY, JSON.stringify(next)); } catch { /* not remembered */ }
    return HttpResponse.json(next);
  })),
  http.get(`${API}/onboarding/state`, scenario(() => HttpResponse.json(ONBOARDING))),
  http.get(`${API}/demo/personas`, scenario(() => HttpResponse.json(PERSONAS))),
  http.post(`${API}/demo/token`, scenario(() => HttpResponse.json({ access_token: "mock-token", expires_in: 3600 }))),

  http.get(`${API}/drop/today`, scenario((s) => HttpResponse.json(dropOf(noDrop(s) ? [] : DROP_CARDS.map((c) => ({ ...c, outcome: answered.get(c.member.id) ?? null })))))),
  http.post(`${API}/drop/today/:id/swipe`, scenario(async (s, { params, request }) => {
    answered.set(Number(params.id), ((await request.json()) as { direction: "intro" | "skip" }).direction);
    return HttpResponse.json(dropOf(noDrop(s) ? [] : DROP_CARDS.map((c) => ({ ...c, outcome: answered.get(c.member.id) ?? null }))));
  })),
  http.get(`${API}/matches`, scenario(async (s, { request }) => {
    if (s === "discover_error") return envelope(500, "internal_error", "Something went wrong on our side.");
    if (s === "discover_loading") await delay("infinite");
    const q = new URL(request.url).searchParams;
    const limit = Number(q.get("limit") ?? 20);
    const offset = Number(q.get("offset") ?? 0);
    const all = s === "empty" ? [] : MATCHES;
    const items = all.slice(offset, offset + limit);
    return HttpResponse.json({ items, count: all.length, next_offset: offset + limit < all.length ? offset + limit : null });
  })),
  http.get(`${API}/intros/path/:id`, scenario((_s, { params }) => {
    const id = Number(params.id);
    if (id === NO_PATH) return envelope(404, "no_warm_path", "You have no mutual connection with this person");
    return HttpResponse.json({ target: person(id), via: id === CONNECTED ? null : person(PEOPLE.lakshmi.id) });
  })),
  http.post(`${API}/intros`, scenario(async (s, { request }) => {
    const { target_id } = (await request.json()) as { target_id: number };
    if (s === "intros_used") return envelope(409, "intro_weekly_limit", "You have used this week's introductions");
    if (target_id === NO_PATH) return envelope(404, "no_warm_path", "You have no mutual connection with this person");
    if (target_id === FULL) return envelope(409, "target_full", "This person is not taking more introductions this week");
    return HttpResponse.json({ ...INTRO, target: person(target_id) }, { status: 201 });
  })),

  http.get(`${API}/livewire`, scenario((s) => HttpResponse.json(s === "empty" ? [] : LIVEWIRE))),
  http.post(`${API}/livewire/seen`, scenario(() => new HttpResponse(null, { status: 204 }))),
  http.get(`${API}/pulse`, scenario((s) => HttpResponse.json(s === "empty" ? { ...PULSE, items: [] } : PULSE))),
  http.post(`${API}/pulse/seen`, scenario(() => new HttpResponse(null, { status: 204 }))),
  http.put(`${API}/posts/:id/reactions/:kind`, scenario(() => new HttpResponse(null, { status: 204 }))),
  http.delete(`${API}/posts/:id/reactions/:kind`, scenario(() => new HttpResponse(null, { status: 204 }))),
  http.post(`${API}/reports`, scenario(async (_s, { request }) => {
    const b = (await request.json()) as { target_type: string; target_id: number };
    return HttpResponse.json({ id: 1, status: "open", target_type: b.target_type, target_id: b.target_id, created_at: new Date().toISOString() }, { status: 201 });
  })),
  http.get(`${API}/notifications/unread-count`, scenario((s) => HttpResponse.json({ count: notifications(s).filter((n) => !n.read).length }))),
  http.get(`${API}/notifications`, scenario((s, { request }) => {
    const q = new URL(request.url).searchParams;
    const limit = Number(q.get("limit") ?? 20);
    const offset = Number(q.get("offset") ?? 0);
    const all = notifications(s).filter((n) => q.get("unread") !== "true" || !n.read);
    return HttpResponse.json({ items: all.slice(offset, offset + limit), count: all.length, next_offset: offset + limit < all.length ? offset + limit : null });
  })),
  http.post(`${API}/notifications/:id/read`, scenario((_s, { params }) => {
    readIds.add(Number(params.id));
    return HttpResponse.json(NOTIFICATIONS.find((n) => n.id === Number(params.id)) ?? NOTIFICATIONS[0]);
  })),

  ...discoverHandlers,
  ...circuitHandlers,
  ...inboxHandlers,
  ...profileHandlers,
  ...postHandlers,
  ...settingsHandlers(me),

  // Anything else: not mocked yet.
  http.all(`${API}/*`, ({ request }) => {
    console.warn(`[mock] ${request.method} ${new URL(request.url).pathname} has no mock handler`);
    return envelope(404, "not_found", "Not mocked.");
  }),
];
