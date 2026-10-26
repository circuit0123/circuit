/**
 * TEMPORARY Circuits fixtures and handlers for mock mode (F5) — replace with the B7 contract fixtures (tests/contract/).
 * Responses are built the way backend/apps/circuits/api.py `_out` builds them, for the signed-in member (Ravi, id 1).
 *
 * Mock rules worth knowing in tests:
 * - Circuit 11 is this week's proposal: You → Priya (fundraising), Priya → Arjun (hiring), Arjun → You (marketing). Priya has said yes.
 *   About 4 seconds after the Circuits list is first loaded, Arjun says yes too and a `circuit:11` / `status` event goes out on the mock
 *   bus, so his segment lights up live. When all three have said yes the circuit is active (the ring closes).
 * - Circuit 10 (last week) is active: your handover to Divya can be marked done, Rohan's to you is done and waiting for your rating,
 *   and Divya's to Rohan isn't done yet (so marking yours done keeps it active).
 * - Circuits 8 and 9 are completed (history). Empty and Under 18 have no circuits (the backend never puts minors in a round).
 */
import { delay, http, HttpResponse, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import { emit } from "./bus";
import { currentScenario, type Scenario } from "./config";
import { PEOPLE } from "./fixtures";

const API = "*/api";
const ME = 1;
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });
const daysAgo = (d: number) => new Date(Date.now() - d * 86_400_000).toISOString();

type Leg = { id: number; giver: number; receiver: number; capability: string; consent: "pending" | "accepted" | "declined"; fulfilled: boolean; rating: number | null };
type Circuit = { id: number; status: "proposed" | "active" | "completed" | "declined" | "expired"; week: string; created_at: string; deadline: string; score: number; legs: Leg[] };

const PERSON: Record<number, Schemas["PersonOut"]> = Object.fromEntries(
  Object.values(PEOPLE).map((p) => [p.id, { id: p.id, display_name: p.display_name, role: p.role, verification_level: p.verification_level }]),
);

const leg = (id: number, giver: number, receiver: number, capability: string, consent: Leg["consent"], fulfilled = false, rating: number | null = null): Leg =>
  ({ id, giver, receiver, capability, consent, fulfilled, rating });

const fresh = (): Circuit[] => [
  {
    id: 11, status: "proposed", week: "2026-W44", created_at: daysAgo(0.4), deadline: new Date(Date.now() + (2 * 24 + 14) * 3600_000 + 120_000).toISOString(), score: 0.81,
    legs: [leg(111, ME, PEOPLE.priya.id, "Fundraising", "pending"), leg(112, PEOPLE.priya.id, PEOPLE.arjun.id, "Hiring", "accepted"), leg(113, PEOPLE.arjun.id, ME, "Marketing", "pending")],
  },
  {
    id: 10, status: "active", week: "2026-W43", created_at: daysAgo(7), deadline: daysAgo(4), score: 0.74,
    legs: [leg(101, ME, PEOPLE.divya.id, "Frontend development", "accepted"), leg(102, PEOPLE.divya.id, PEOPLE.rohan.id, "Climate data", "accepted"), leg(103, PEOPLE.rohan.id, ME, "Pitch deck", "accepted", true)],
  },
  {
    id: 9, status: "completed", week: "2026-W38", created_at: "2026-09-16T05:00:00Z", deadline: "2026-09-19T05:00:00Z", score: 0.7,
    legs: [leg(91, ME, PEOPLE.sneha.id, "React", "accepted", true, 5), leg(92, PEOPLE.sneha.id, PEOPLE.asha.id, "Design", "accepted", true, 4), leg(93, PEOPLE.asha.id, ME, "Product thinking", "accepted", true, 5)],
  },
  {
    id: 8, status: "completed", week: "2026-W33", created_at: "2026-08-12T05:00:00Z", deadline: "2026-08-15T05:00:00Z", score: 0.66,
    legs: [leg(81, ME, PEOPLE.kavya.id, "Web app", "accepted", true, 4), leg(82, PEOPLE.kavya.id, PEOPLE.lakshmi.id, "Lab access", "accepted", true, 5), leg(83, PEOPLE.lakshmi.id, ME, "Sales", "accepted", true, 5)],
  },
];

let store: Circuit[] = fresh();
let liveTimer: ReturnType<typeof setTimeout> | null = null;

/** After this many ms Arjun answers circuit 11 (the live update). */
const ARJUN_ANSWERS_MS = 4000;

const settle = (c: Circuit) => {
  if (c.status === "proposed" && c.legs.some((l) => l.consent === "declined")) c.status = "declined";
  else if (c.status === "proposed" && c.legs.every((l) => l.consent === "accepted")) c.status = "active";
  else if (c.status === "active" && c.legs.every((l) => l.fulfilled)) c.status = "completed";
};

function nextStep(c: Circuit, mine: Leg, got: Leg): Schemas["CircuitOut"]["next_step"] {
  const unrated = got.fulfilled && got.rating === null;
  if (c.status === "proposed") return mine.consent === "pending" ? "answer" : "waiting";
  if (c.status === "active") return !mine.fulfilled ? "mark_done" : unrated ? "rate" : "waiting";
  if (c.status === "completed" && unrated) return "rate";
  return "none";
}

function out(c: Circuit): Schemas["CircuitOut"] {
  const mine = c.legs.find((l) => l.giver === ME)!;
  const got = c.legs.find((l) => l.receiver === ME)!;
  const active = c.status === "active";
  return {
    id: c.id, status: c.status, score_percent: Math.round(c.score * 100), week: c.week, consent_deadline: c.deadline, created_at: c.created_at,
    time_left_seconds: c.status === "proposed" ? Math.max(0, Math.floor((new Date(c.deadline).getTime() - Date.now()) / 1000)) : null,
    my_consent: mine.consent,
    next_step: nextStep(c, mine, got),
    you_help: { person: PERSON[mine.receiver], capability: mine.capability },
    helps_you: { person: PERSON[got.giver], capability: got.capability },
    members: c.legs.map((l) => ({ person: PERSON[l.giver], is_me: l.giver === ME, consent: l.consent, done: l.fulfilled })),
    legs: c.legs.map((l) => ({
      id: l.id, giver: PERSON[l.giver], receiver: PERSON[l.receiver], capability: l.capability, consent: l.consent, fulfilled: l.fulfilled,
      rated: l.rating !== null, rating: l.giver === ME || l.receiver === ME ? l.rating : null, i_give: l.giver === ME, i_receive: l.receiver === ME,
      can_mark_done: l.giver === ME && active && !l.fulfilled,
      can_rate: l.receiver === ME && l.fulfilled && l.rating === null && (active || c.status === "completed"),
    })),
  };
}

const none = () => ["empty", "under18"].includes(currentScenario());
const find = (id: unknown) => (none() ? undefined : store.find((c) => c.id === Number(id)));

/** Arjun's answer, once per page load, a few seconds after the list is first shown. */
function scheduleLiveAnswer() {
  if (liveTimer || none()) return;
  liveTimer = setTimeout(() => {
    const c = store.find((x) => x.id === 11);
    const l = c?.legs.find((x) => x.giver === PEOPLE.arjun.id);
    if (!c || !l || c.status !== "proposed") return;
    l.consent = "accepted";
    settle(c);
    emit("circuit:11", "status", { circuit_id: 11 });
  }, ARJUN_ANSWERS_MS);
}

/** Wait or fail the way the scenario says (same as handlers.ts). */
function scenario(fn: (s: Scenario, info: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => Response | Promise<Response>) {
  return async (info: { request: Request; params: Record<string, string | readonly string[] | undefined> }): Promise<Response> => {
    const s = currentScenario();
    if (s === "loading" || s === "connect_loading") await delay("infinite");
    if (s === "slow3g") await delay(2000);
    if (s === "error" || s === "connect_error") return envelope(500, "internal_error", "Something went wrong on our side.");
    return fn(s, info);
  };
}

export const circuitHandlers: HttpHandler[] = [
    http.get(`${API}/circuits`, scenario(() => {
      const items = none() ? [] : store.filter((c) => c.status !== "declined" && c.status !== "expired").sort((a, b) => b.id - a.id).map(out);
      scheduleLiveAnswer();
      return HttpResponse.json({ items, count: items.length, next_offset: null });
    })),
    http.get(`${API}/circuits/:id`, scenario((_s, { params }) => {
      const c = find(params.id);
      return c ? HttpResponse.json(out(c)) : envelope(404, "not_found", "Not found");
    })),
    http.post(`${API}/circuits/:id/respond`, scenario(async (_s, { params, request }) => {
      const c = find(params.id);
      if (!c) return envelope(404, "not_found", "Not found");
      if (c.status !== "proposed") return envelope(409, "circuit_expired", "This proposal has expired");
      const { accept } = (await request.json()) as { accept: boolean };
      c.legs.find((l) => l.giver === ME)!.consent = accept ? "accepted" : "declined";
      settle(c);
      return HttpResponse.json(out(c));
    })),
    http.post(`${API}/circuits/:id/legs/:leg/done`, scenario((_s, { params }) => {
      const c = find(params.id);
      const l = c?.legs.find((x) => x.id === Number(params.leg) && x.giver === ME);
      if (!c || !l) return envelope(404, "not_found", "Not found");
      l.fulfilled = true;
      settle(c);
      return HttpResponse.json(out(c));
    })),
    http.post(`${API}/circuits/:id/legs/:leg/rating`, scenario(async (_s, { params, request }) => {
      const c = find(params.id);
      const l = c?.legs.find((x) => x.id === Number(params.leg) && x.receiver === ME);
      if (!c || !l) return envelope(404, "not_found", "Not found");
      if (l.rating === null) l.rating = ((await request.json()) as { rating: number }).rating;
      return HttpResponse.json(out(c));
    })),
];

/** For tests of the mock itself: start over. */
export const resetCircuits = () => { store = fresh(); if (liveTimer) clearTimeout(liveTimer); liveTimer = null; };
