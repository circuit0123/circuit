import { delay, http, HttpResponse, type HttpHandler, type HttpResponseResolver } from "msw";
import type { Schemas } from "@circuit/api-client";
import { currentScenario, type Scenario } from "./config";
import { CONFIG, DROP_CARDS, INTRO, LIVEWIRE, MATCHES, ME, ONBOARDING, PERSONAS, PULSE, dropOf } from "./fixtures";

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
  const base = { ...ME, appearance: readAppearance() };
  if (s === "beta") return { ...base, beta_access: false };
  if (s === "under18") return { ...base, is_minor: true, allow_requests: false, profile_visibility: "organisation", bio: "Class 12 student. I build small apps for my school robotics club." };
  return base;
}

function config(s: Scenario): Schemas["ConfigOut"] {
  if (s === "beta") return { ...CONFIG, beta_mode: true, beta_access: false };
  if (s === "features_off") return { ...CONFIG, features: Object.fromEntries(Object.keys(CONFIG.features).map((k) => [k, false])) };
  return CONFIG;
}

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
  http.get(`${API}/matches`, scenario((s, { request }) => {
    const q = new URL(request.url).searchParams;
    const limit = Number(q.get("limit") ?? 20);
    const offset = Number(q.get("offset") ?? 0);
    const all = s === "empty" ? [] : MATCHES;
    const items = all.slice(offset, offset + limit);
    return HttpResponse.json({ items, count: all.length, next_offset: offset + limit < all.length ? offset + limit : null });
  })),
  http.post(`${API}/intros`, scenario(() => HttpResponse.json(INTRO))),

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
  http.get(`${API}/notifications/unread-count`, scenario((s) => HttpResponse.json({ count: s === "empty" ? 0 : 3 }))),

  // Anything else: not mocked yet.
  http.all(`${API}/*`, ({ request }) => {
    console.warn(`[mock] ${request.method} ${new URL(request.url).pathname} has no mock handler`);
    return envelope(404, "not_found", "Not mocked.");
  }),
];
