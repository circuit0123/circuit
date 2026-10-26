/**
 * TEMPORARY Inbox fixtures and handlers for mock mode (F5): conversations, messages, image uploads, accept, block, read, connections
 * — replace with the B7 contract fixtures (tests/contract/). Typed against the generated API types.
 *
 * Mock rules worth knowing in tests:
 * - Chats: Meera Krishnan (501, unread), Farhan Ali (502, unread), Divya Subramanian (503), Arun Prakash (504), Ishaan Reddy (505).
 *   Requests: Rohan Gupta (506, unread) and Sneha Pillai (507). Under 18: no requests. Empty: nothing at all.
 * - Live: about 5 seconds after the Inbox is first loaded, Farhan sends "Also, is the repo public?" (event `message` on
 *   `conversation:502` on the mock bus). After you send in a chat, the other person replies once, about 2 seconds later.
 * - "Messages fail to send" (send_fails): the first try of every message fails; Retry sends it.
 * - Connections ("New message"): the five chat people plus Dr. Lakshmi Narayanan (7), who has no conversation yet.
 * - Uploads (shared with build logs, F6): each PUT takes about half a second; "Uploads fail once" (upload_fails) fails the first try of
 *   each picture.
 * - Decline (POST …/decline) is a mock-only stand-in: the API has no such call yet (PROGRESS.md "Frontend → API needed").
 */
import { delay, http, HttpResponse, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import { emit } from "./bus";
import { currentScenario, type Scenario } from "./config";
import { author, PEOPLE } from "./fixtures";

const API = "*/api";
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });
const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

type Author = Schemas["AuthorOut"];
type Msg = Omit<Schemas["MessageOut"], "conversation_id"> & { read: boolean };
type Conv = { id: number; other: Author; status: "request" | "active"; started_by_me: boolean; messages: Msg[] };

export const INBOX_PEOPLE = {
  meera: author(21, "Meera Krishnan", "mentor", "Ex-founder, offline-first apps", "Chennai", 3),
  farhan: author(22, "Farhan Ali", "student", "Maps and mobile, final year", "Chennai", 1),
  divyaS: author(23, "Divya Subramanian", "founder", "School attendance on WhatsApp", "Madurai", 2),
  arun: author(24, "Arun Prakash", "founder", "Organises the SVIT demo day", "Chennai", 2),
  ishaan: author(25, "Ishaan Reddy", "student", "Backend, Django and Postgres", "Hyderabad", 1),
};

let nextId = 9000;
const m = (mine: boolean, body: string, minutes: number, read = true): Msg => ({ id: ++nextId, mine, body, image: null, removed: false, created_at: minutesAgo(minutes), read: mine || read });

const fresh = (): Conv[] => [
  { id: 501, other: INBOX_PEOPLE.meera, status: "active", started_by_me: false, messages: [
    m(false, "Saw your farm map build log. Nicely done.", 26 * 60),
    m(true, "Thank you. I'm stuck on the backend for offline sync.", 25 * 60),
    m(false, "Sakthi is great at exactly that. Want me to introduce you?", 40, false),
    m(false, "Happy to intro you to Sakthi this week.", 12, false),
  ] },
  { id: 502, other: INBOX_PEOPLE.farhan, status: "active", started_by_me: false, messages: [
    m(true, "The pins load from one GeoJSON file now.", 3 * 60),
    m(false, "Can you share the map prototype?", 95, false),
  ] },
  { id: 503, other: INBOX_PEOPLE.divyaS, status: "active", started_by_me: true, messages: [
    m(true, "Try sending the reminder at 7 pm, when parents are home.", 30 * 60),
    m(false, "Thanks, that helped a lot.", 29 * 60),
  ] },
  { id: 504, other: INBOX_PEOPLE.arun, status: "active", started_by_me: false, messages: [
    m(false, "Your team is on at 3:40 pm, after the agritech teams.", 3 * 24 * 60 + 20),
    m(false, "See you at the demo day.", 3 * 24 * 60),
  ] },
  { id: 505, other: INBOX_PEOPLE.ishaan, status: "active", started_by_me: true, messages: [
    m(true, "Could you look at my sync endpoint?", 5 * 24 * 60 + 30),
    m(false, "Sent the repo link.", 5 * 24 * 60),
  ] },
  { id: 506, other: PEOPLE.rohan, status: "request", started_by_me: false, messages: [
    m(false, "Hi Ravi, Lakshmi said you built the stock screens for Aravind. Could I ask you two questions about offline sync?", 50, false),
  ] },
  { id: 507, other: PEOPLE.sneha, status: "request", started_by_me: false, messages: [
    m(false, "Saw your build log on the map prototype. Would you test our onboarding this week?", 2 * 24 * 60),
  ] },
];

let store: Conv[] = fresh();
const uploads = new Map<number, { src: string; width: number; height: number }>();
const failedUploads = new Set<number>();
/** What an upload id holds (posts.ts builds post media from it). */
export const uploadOf = (id: number) => uploads.get(id);
const failedOnce = new Set<string>();
const replied = new Set<number>();
let liveTimer: ReturnType<typeof setTimeout> | null = null;
const CONNECTIONS: Author[] = [...Object.values(INBOX_PEOPLE), PEOPLE.lakshmi];

const REPLIES: Record<number, string> = {
  501: "Good. I'll write to Sakthi tonight.",
  502: "Got it, thanks. I'll try it on my phone.",
  503: "Will do. I'll tell you how the week goes.",
  504: "Noted. See you there.",
  505: "Looking at it now.",
};

/** Under-18 members never get requests from strangers (backend rule). */
const visible = (s: Scenario) => (s === "empty" ? [] : s === "under18" ? store.filter((c) => c.status !== "request") : store);

const msgOut = (c: Conv, x: Msg): Schemas["MessageOut"] => ({ id: x.id, conversation_id: c.id, mine: x.mine, body: x.body, image: x.image, removed: x.removed, created_at: x.created_at });
const convOut = (c: Conv): Schemas["ConversationOut"] => {
  const last = c.messages[c.messages.length - 1] ?? null;
  return {
    id: c.id, status: c.status, other: c.other, started_by_me: c.started_by_me,
    last_message_at: last?.created_at ?? null,
    unread: c.messages.filter((x) => !x.mine && !x.read).length,
    last_message: last ? msgOut(c, last) : null,
  };
};

function arrive(c: Conv, body: string) {
  const msg: Msg = { id: ++nextId, mine: false, body, image: null, removed: false, created_at: new Date().toISOString(), read: false };
  c.messages.push(msg);
  emit(`conversation:${c.id}`, "message", { message_id: msg.id, conversation_id: c.id });
}

/** Farhan's new message, once per page load, a few seconds after the Inbox first loads. */
function scheduleLive(s: Scenario) {
  if (liveTimer || s === "empty") return;
  liveTimer = setTimeout(() => {
    const c = store.find((x) => x.id === 502);
    if (c) arrive(c, "Also, is the repo public?");
  }, 5000);
}

/** Wait or fail the way the scenario says (same as handlers.ts); `connect_loading` / `connect_error` hit only Circuits and Inbox. */
function scenario(fn: (s: Scenario, info: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => Response | Promise<Response>) {
  return async (info: { request: Request; params: Record<string, string | readonly string[] | undefined> }): Promise<Response> => {
    const s = currentScenario();
    if (s === "loading" || s === "connect_loading") await delay("infinite");
    if (s === "slow3g") await delay(2000);
    if (s === "error" || s === "connect_error") return envelope(500, "internal_error", "Something went wrong on our side.");
    return fn(s, info);
  };
}

const find = (s: Scenario, id: unknown) => visible(s).find((c) => c.id === Number(id));
const notFound = () => envelope(404, "not_found", "Not found");

export const inboxHandlers: HttpHandler[] = [
  http.get(`${API}/conversations`, scenario((s, { request }) => {
    const folder = new URL(request.url).searchParams.get("folder") ?? "chats";
    scheduleLive(s);
    const rows = visible(s)
      .filter((c) => (folder === "requests" ? c.status === "request" : c.status === "active")) // the backend keeps sent and received requests in Requests
      .map(convOut)
      .sort((a, b) => (b.last_message_at ?? "").localeCompare(a.last_message_at ?? ""));
    return HttpResponse.json(rows);
  })),
  http.post(`${API}/conversations`, scenario(async (s, { request }) => {
    const b = (await request.json()) as { member_id: number; body: string; upload_id: number | null };
    const other = CONNECTIONS.find((a) => a.id === b.member_id) ?? Object.values(PEOPLE).find((a) => a.id === b.member_id);
    if (!other || s === "empty") return notFound();
    let c = store.find((x) => x.other.id === other.id);
    if (!c) {
      c = { id: 600 + other.id, other, status: CONNECTIONS.includes(other) ? "active" : "request", started_by_me: true, messages: [] };
      store.push(c);
    }
    const msg: Msg = { id: ++nextId, mine: true, body: b.body, image: b.upload_id ? imageOf(b.upload_id) : null, removed: false, created_at: new Date().toISOString(), read: true };
    c.messages.push(msg);
    return HttpResponse.json({ conversation: convOut(c), message: msgOut(c, msg) }, { status: 201 });
  })),
  http.get(`${API}/conversations/:id`, scenario((s, { params }) => {
    const c = find(s, params.id);
    return c ? HttpResponse.json(convOut(c)) : notFound();
  })),
  http.get(`${API}/conversations/:id/messages/:mid`, scenario((s, { params }) => {
    const c = find(s, params.id);
    const x = c?.messages.find((y) => y.id === Number(params.mid));
    return c && x ? HttpResponse.json(msgOut(c, x)) : notFound();
  })),
  http.get(`${API}/conversations/:id/messages`, scenario((s, { params, request }) => {
    const c = find(s, params.id);
    if (!c) return notFound();
    const q = new URL(request.url).searchParams;
    const limit = Number(q.get("limit") ?? 20);
    const before = q.get("cursor") ? Number(q.get("cursor")) : Infinity;
    const older = c.messages.filter((x) => x.id < before).reverse(); // newest first
    const items = older.slice(0, limit);
    const more = older.length > limit;
    return HttpResponse.json({ items: items.map((x) => msgOut(c, x)), next_cursor: more ? String(items[items.length - 1].id) : null });
  })),
  http.post(`${API}/conversations/:id/messages`, scenario(async (s, { params, request }) => {
    const c = find(s, params.id);
    if (!c) return notFound();
    const b = (await request.json()) as { body: string; upload_id: number | null };
    const tryKey = `${c.id}|${b.body}|${b.upload_id ?? ""}`;
    if (s === "send_fails" && !failedOnce.has(tryKey)) {
      failedOnce.add(tryKey);
      return envelope(500, "internal_error", "Something went wrong on our side.");
    }
    if (c.status === "request" && c.started_by_me && c.messages.some((x) => x.mine)) return envelope(409, "request_pending", "Wait for them to accept your first message");
    if (c.status === "request" && !c.started_by_me) c.status = "active"; // answering a request accepts it
    const msg: Msg = { id: ++nextId, mine: true, body: b.body, image: b.upload_id ? imageOf(b.upload_id) : null, removed: false, created_at: new Date().toISOString(), read: true };
    c.messages.push(msg);
    if (c.status === "active" && REPLIES[c.id] && !replied.has(c.id)) {
      replied.add(c.id);
      const conv = c;
      setTimeout(() => arrive(conv, REPLIES[conv.id]), 2000);
    }
    return HttpResponse.json(msgOut(c, msg), { status: 201 });
  })),
  http.post(`${API}/conversations/:id/accept`, scenario((s, { params }) => {
    const c = find(s, params.id);
    if (!c || c.status !== "request" || c.started_by_me) return notFound();
    c.status = "active";
    return HttpResponse.json(convOut(c));
  })),
  http.post(`${API}/conversations/:id/block`, scenario((s, { params }) => {
    const c = find(s, params.id);
    if (!c) return notFound();
    store = store.filter((x) => x.id !== c.id);
    return new HttpResponse(null, { status: 204 });
  })),
  // Mock-only stand-in (API needed): say no to a request without blocking.
  http.post(`${API}/conversations/:id/decline`, scenario((s, { params }) => {
    const c = find(s, params.id);
    if (!c || c.status !== "request") return notFound();
    store = store.filter((x) => x.id !== c.id);
    return new HttpResponse(null, { status: 204 });
  })),
  http.post(`${API}/conversations/:id/read`, scenario((s, { params }) => {
    const c = find(s, params.id);
    if (!c) return notFound();
    let marked = 0;
    for (const x of c.messages) if (!x.mine && !x.read) { x.read = true; marked++; }
    return HttpResponse.json({ marked });
  })),
  http.get(`${API}/connections`, scenario((s) => HttpResponse.json(s === "empty" ? [] : CONNECTIONS))),
  // Image uploads: a signed URL that this mock answers, so the picture really shows.
  http.post(`${API}/media/uploads`, scenario(() => {
    const id = ++nextId;
    return HttpResponse.json({ id, upload_url: `${location.origin}/mock-storage/uploads/${id}`, status: "pending" }, { status: 201 });
  })),
  http.put("*/mock-storage/uploads/:id", async ({ params, request }) => {
    const blob = await request.blob();
    await delay(currentScenario() === "slow3g" ? 2500 : 500); // long enough to see the progress bar
    // "Uploads fail once": the first try of each picture fails (the same picture comes back the same size), and Retry sends it.
    if (currentScenario() === "upload_fails" && !failedUploads.has(blob.size)) {
      failedUploads.add(blob.size);
      return new HttpResponse(null, { status: 500 });
    }
    const src = await new Promise<string>((resolve) => { const r = new FileReader(); r.onload = () => resolve(String(r.result)); r.readAsDataURL(blob); });
    let width = 4, height = 3;
    try { const bmp = await createImageBitmap(blob); width = bmp.width; height = bmp.height; bmp.close(); } catch { /* keep 4:3 */ }
    uploads.set(Number(params.id), { src, width, height });
    return new HttpResponse(null, { status: 200 });
  }),
  http.post(`${API}/media/uploads/:id/complete`, scenario((_s, { params }) => {
    const u = uploads.get(Number(params.id));
    return HttpResponse.json({ id: Number(params.id), status: "ready", width: u?.width ?? null, height: u?.height ?? null });
  })),
];

function imageOf(uploadId: number): Record<string, unknown> | null {
  const u = uploads.get(uploadId);
  return u ? { width: u.width, height: u.height, w480: u.src, w1440: u.src } : null;
}
