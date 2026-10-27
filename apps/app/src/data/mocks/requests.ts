/**
 * TEMPORARY mock handlers for answering intros and connection requests (H4): the lists, accept/decline and the rating, shaped like
 * packages/api-client/fixtures/intros/* and profile/connect_*. Only the "Waiting for you" scenario (`requests`) has anything in it; every
 * other scenario has empty lists, as a member with nothing waiting would.
 *
 * Mock rules worth knowing in tests (requests scenario):
 * - Connection requests: Divya Menon (8, with a note) and Rohan Gupta (6, no note).
 * - Intros through you (broker): Asha Raman (2) wants to meet Dr. Kavya Subramanian (5). Intros for you (target): Sneha Pillai (9) via Dr. Lakshmi.
 * - Intros you asked for: Arjun Mehta (4, accepted, not rated yet) and Priya Nair (3, waiting for Dr. Lakshmi to pass it on).
 */
import { http, HttpResponse, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import { currentScenario } from "./config";
import { PEOPLE } from "./fixtures";

const API = "*/api";
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });
const person = (p: { id: number; display_name: string; role: string; verification_level: number }): Schemas["PersonOut"] => ({ id: p.id, display_name: p.display_name, role: p.role, verification_level: p.verification_level, photo: null });
const ago = (h: number) => new Date(Date.now() - h * 3600_000).toISOString();
const soon = (h: number) => new Date(Date.now() + h * 3600_000).toISOString();

type Intro = Schemas["IntroOut"];
const intro = (id: number, my_role: Intro["my_role"], stage: string, status: string, requester: typeof PEOPLE.me, target: typeof PEOPLE.me, via: typeof PEOPLE.me | null, message: string): Intro => ({
  id, my_role, stage, status, can_respond: my_role !== "requester" && status === "pending", requester: person(requester), target: person(target), via: via ? person(via) : null,
  message, outcome_rating: null, created_at: ago(5), expires_at: soon(24 * 6),
});

const freshIntros = (): Intro[] => [
  intro(1, "broker", "broker", "pending", PEOPLE.asha, PEOPLE.kavya, null, "We both sell to hospital labs and I think you two should talk."),
  intro(2, "target", "target", "pending", PEOPLE.sneha, PEOPLE.me, PEOPLE.lakshmi, "I'd love a design review of my sign-up flow."),
  intro(3, "requester", "done", "accepted", PEOPLE.me, PEOPLE.arjun, null, "Hiring a frontend intern? I build in React."),
  intro(4, "requester", "broker", "pending", PEOPLE.me, PEOPLE.priya, PEOPLE.lakshmi, "Could I learn how you ran your first pilot?"),
];

type Req = Schemas["ConnectionRequestOut"];
const freshRequests = (): Req[] => [
  { id: 71, sender: PEOPLE.divya, recipient: PEOPLE.me, note: "Loved your farm map build log.", status: "pending", created_at: ago(3) },
  { id: 72, sender: PEOPLE.rohan, recipient: PEOPLE.me, note: "", status: "pending", created_at: ago(9) },
];

let intros = freshIntros();
let requests = freshRequests();
let seen: string | null = null;
/** Each scenario load starts from the same lists, so a test that answers one doesn't change the next. */
const sync = () => {
  const s = currentScenario();
  if (s !== seen) { seen = s; intros = freshIntros(); requests = freshRequests(); }
  return s === "requests";
};

const BOX: Record<string, Intro["my_role"]> = { received: "target", brokered: "broker", sent: "requester" };

export const requestHandlers: HttpHandler[] = [
  http.get(`${API}/intros`, ({ request }) => {
    const on = sync();
    const items = on ? intros.filter((i) => i.my_role === BOX[new URL(request.url).searchParams.get("box") ?? "sent"]) : [];
    return HttpResponse.json({ items, count: items.length, next_offset: null });
  }),
  http.post(`${API}/intros/:id/respond`, async ({ params, request }) => {
    sync();
    const i = intros.find((x) => x.id === Number(params.id));
    if (!i) return envelope(404, "not_found", "Not found");
    const { accept } = (await request.json()) as { accept: boolean };
    if (!i.can_respond) return envelope(409, "not_your_turn", "It isn't your turn");
    const next: Intro = !accept ? { ...i, can_respond: false, status: "declined", stage: "stopped" }
      : i.my_role === "broker" ? { ...i, can_respond: false, stage: "target" }
      : { ...i, can_respond: false, status: "accepted", stage: "done" };
    intros = intros.map((x) => (x.id === i.id ? next : x));
    return HttpResponse.json(next);
  }),
  http.post(`${API}/intros/:id/rating`, async ({ params, request }) => {
    sync();
    const i = intros.find((x) => x.id === Number(params.id));
    if (!i) return envelope(404, "not_found", "Not found");
    if (i.status !== "accepted") return envelope(409, "intro_not_accepted", "Not accepted yet");
    const { rating } = (await request.json()) as { rating: number };
    const next = { ...i, outcome_rating: rating };
    intros = intros.map((x) => (x.id === i.id ? next : x));
    return HttpResponse.json(next);
  }),
  http.get(`${API}/connections/requests`, ({ request }) => {
    const on = sync();
    const box = new URL(request.url).searchParams.get("box") ?? "incoming";
    return HttpResponse.json(on && box === "incoming" ? requests.filter((r) => r.status === "pending") : []);
  }),
  http.post(`${API}/connections/requests/:id/respond`, async ({ params, request }) => {
    sync();
    const r = requests.find((x) => x.id === Number(params.id));
    if (!r) return envelope(404, "not_found", "Not found");
    if (r.status !== "pending") return envelope(409, "already_answered", "Already answered");
    const { accept } = (await request.json()) as { accept: boolean };
    const next: Req = { ...r, status: accept ? "accepted" : "declined" };
    requests = requests.map((x) => (x.id === r.id ? next : x));
    return HttpResponse.json(next);
  }),
  http.delete(`${API}/connections/:id`, () => new HttpResponse(null, { status: 204 })),
];
