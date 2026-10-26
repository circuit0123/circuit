/**
 * TEMPORARY build log fixtures and handlers for mock mode (F6): one post, a member's posts, creating and deleting, and replies — replace with
 * the B7 contract fixtures (tests/contract/). Typed against the generated API types. (Reactions and reports stay in handlers.ts.)
 *
 * Mock rules worth knowing in tests:
 * - "Profile and Settings loading" (you_loading) and "… fail to load" (you_error) hit only this file's endpoints (the app itself opens).
 * - 101 is Arjun's stock-alert build log (one picture), with a reply from Dr. Lakshmi and Arjun's answer under it.
 * - 201 is yours ("Farm map v2", two pictures), so it shows your private totals (4 found it helpful, 1 asked for an intro, 1 reply) and
 *   Delete instead of Report; 202 is yours too, text only. Asha (2) has one build log (301).
 * - Empty and "Profile to fill in": nobody has build logs (a post opened by id still loads).
 * - A new build log gets the next id from 900 and shows up in your profile's grid; its pictures are the ones you uploaded.
 */
import { http, HttpResponse, delay, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import { currentScenario, type Scenario } from "./config";
import { author, PEOPLE, POST } from "./fixtures";
import { INBOX_PEOPLE, uploadOf } from "./inbox";

const API = "*/api";
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });
const minutesAgo = (m: number) => new Date(Date.now() - m * 60_000).toISOString();
type Info = { request: Request; params: Record<string, string | readonly string[] | undefined> };

function scenario(fn: (s: Scenario, info: Info) => Response | Promise<Response>) {
  return async (info: Info): Promise<Response> => {
    const s = currentScenario();
    if (s === "loading" || s === "you_loading") await delay("infinite");
    if (s === "slow3g") await delay(2000);
    if (s === "error" || s === "you_error") return envelope(500, "internal_error", "Something went wrong on our side.");
    return fn(s, info);
  };
}

/** A build-log picture: a map or a dashboard with real labels, as inline SVG (DESIGN.md §5 Imagery). */
function picture(title: string, rows: Array<[string, string]>, w = 720, h = 900) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" font-family="Arial, sans-serif"><rect width="${w}" height="${h}" fill="#0b1f18"/><text x="36" y="110" font-size="30" font-weight="700" fill="#f3eef5">${title}</text>${rows.map((r, i) => `<g transform="translate(36 ${170 + i * 96})"><rect width="${w - 72}" height="76" rx="12" fill="#142c23"/><text x="22" y="47" font-size="24" fill="#f3eef5">${r[0]}</text><text x="${w - 220}" y="47" font-size="24" fill="#2fbf8a">${r[1]}</text></g>`).join("")}</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
}
const media = (src: string, alt: string, width = 720, height = 900) => ({ w480: src, w1440: src, alt_text: alt, width, height });

type Stored = Schemas["PostOut"];
const RAVI_STATS = { reactions: { helpful: 4, intro_me: 1 }, replies: 1 };

const seed = (): Stored[] => [
  { ...POST, private_stats: null },
  {
    id: 201, author: PEOPLE.me, created_at: minutesAgo(60 * 26), status: "visible", visibility: "everyone", my_reactions: [], link: "https://github.com/ravikumar/farm-map",
    body: "Farm map v2: plots, wells and soil tests on one screen. It loads from one GeoJSON file now, so it works on a slow phone in the field.",
    capabilities: [{ slug: "maps", name: "Maps" }, { slug: "frontend-dev", name: "Frontend development" }],
    media: [
      media(picture("Farm map · Thiruvallur", [["Plots mapped", "126"], ["Wells", "18"], ["Soil tests", "41"], ["Offline", "Yes"]]), "Farm map summary: 126 plots, 18 wells and 41 soil tests, working offline"),
      media(picture("Plot 42 · Ponneri", [["Crop", "Paddy"], ["Last test", "12 Oct"], ["Moisture", "31%"]]), "One plot's details: paddy, last soil test on 12 October, moisture 31 percent"),
    ],
    private_stats: RAVI_STATS,
  },
  {
    id: 202, author: PEOPLE.me, created_at: minutesAgo(60 * 24 * 4), status: "visible", visibility: "connections", my_reactions: [], link: "", media: [],
    body: "Learned how to cache map tiles in a service worker. The farm map opens in under a second on the second visit.",
    capabilities: [{ slug: "frontend-dev", name: "Frontend development" }], private_stats: { reactions: {}, replies: 0 },
  },
  {
    id: 301, author: PEOPLE.asha, created_at: minutesAgo(60 * 30), status: "visible", visibility: "everyone", my_reactions: [], link: "",
    body: "First test with 40 farmers near Hosur: the assistant understood 92% of what they asked in Kannada.",
    capabilities: [{ slug: "ml", name: "Machine learning" }],
    media: [media(picture("Kannada voice · test run", [["Words understood", "92%"], ["Speakers", "40"], ["Dialects", "3"]], 720, 720), "Test run summary: 92 percent understood, 40 speakers, 3 dialects", 720, 720)],
    private_stats: null,
  },
];

let posts = seed();
let nextId = 900;
let nextReply = 5000;

const reply = (id: number, who: Schemas["AuthorOut"], body: string, minutes: number, replies: Schemas["ReplyOut"][] = []): Schemas["ReplyOut"] => ({ id, author: who, body, created_at: minutesAgo(minutes), replies });
const replies = new Map<number, Schemas["ReplyOut"][]>([
  [101, [reply(4001, PEOPLE.lakshmi, "Which stock level sets off the alert? Pharmacists I know want a warning a week ahead.", 80, [reply(4002, PEOPLE.arjun, "Seven days of average sales. They can change it per item.", 60)])]],
  [201, [reply(4003, INBOX_PEOPLE.meera, "The offline part is the hard bit. Nicely done.", 600)]],
]);

const noPosts = (s: Scenario) => s === "empty" || s === "profile_empty";
const find = (id: unknown) => posts.find((p) => p.id === Number(id));
const out = (p: Stored, viewer = PEOPLE.me.id): Stored => ({ ...p, private_stats: p.author.id === viewer ? p.private_stats ?? { reactions: {}, replies: replies.get(p.id)?.length ?? 0 } : null });

export const postHandlers: HttpHandler[] = [
  http.get(`${API}/posts/:id/replies`, scenario((_s, { params }) => (find(params.id) ? HttpResponse.json(replies.get(Number(params.id)) ?? []) : envelope(404, "not_found", "Not found")))),
  http.post(`${API}/posts/:id/replies`, scenario(async (_s, { params, request }) => {
    const p = find(params.id);
    if (!p) return envelope(404, "not_found", "Not found");
    const b = (await request.json()) as Schemas["ReplyIn"];
    if (!b.body?.trim() || b.body.length > 300) return envelope(422, "invalid", "A reply is 1 to 300 characters");
    const r = reply(++nextReply, PEOPLE.me, b.body, 0);
    const list = replies.get(p.id) ?? [];
    if (b.parent_id) {
      const parent = list.find((x) => x.id === b.parent_id);
      if (!parent) return envelope(422, "invalid", "Replies go one level deep");
      parent.replies.push(r);
    } else list.push(r);
    replies.set(p.id, list);
    return HttpResponse.json(r, { status: 201 });
  })),
  http.delete(`${API}/replies/:id`, scenario((_s, { params }) => {
    const id = Number(params.id);
    for (const [k, list] of replies) replies.set(k, list.filter((x) => x.id !== id).map((x) => ({ ...x, replies: x.replies.filter((c) => c.id !== id) })));
    return new HttpResponse(null, { status: 204 });
  })),
  http.get(`${API}/posts/:id`, scenario((_s, { params }) => {
    const p = find(params.id);
    return p ? HttpResponse.json(out(p)) : envelope(404, "not_found", "Not found");
  })),
  http.delete(`${API}/posts/:id`, scenario((_s, { params }) => {
    posts = posts.filter((p) => p.id !== Number(params.id));
    return new HttpResponse(null, { status: 204 });
  })),
  http.get(`${API}/members/:id/posts`, scenario((s, { params }) => {
    if (noPosts(s) && !posts.some((p) => p.id >= 900)) return HttpResponse.json({ items: [], next_cursor: null });
    const items = posts.filter((p) => p.author.id === Number(params.id) && (!noPosts(s) || p.id >= 900)).sort((a, b) => b.created_at.localeCompare(a.created_at)).map((p) => out(p));
    return HttpResponse.json({ items, next_cursor: null });
  })),
  http.post(`${API}/posts`, scenario(async (s, { request }) => {
    const b = (await request.json()) as Schemas["PostIn"];
    if (s === "under18" && b.visibility === "everyone") return envelope(403, "under_18_restricted", "Public posting opens once your age is verified");
    const caps = (b.capabilities ?? []).map((slug) => ({ slug, name: slug.split("-").map((w, i) => (i === 0 ? w[0].toUpperCase() + w.slice(1) : w)).join(" ") }));
    const p: Stored = {
      id: ++nextId, author: s === "under18" ? author(1, "Ravi Kumar", "student", "Class 12, school robotics club") : PEOPLE.me, created_at: new Date().toISOString(), status: "visible",
      visibility: b.visibility, body: b.body ?? "", link: b.link ?? "", capabilities: caps, my_reactions: [], private_stats: { reactions: {}, replies: 0 },
      media: (b.media ?? []).map((m) => { const u = uploadOf(m.upload_id); return media(u?.src ?? "", m.alt_text, u?.width ?? 4, u?.height ?? 5); }),
    };
    posts = [p, ...posts];
    return HttpResponse.json(out(p), { status: 201 });
  })),
];
