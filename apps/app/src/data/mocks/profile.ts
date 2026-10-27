/**
 * TEMPORARY profile fixtures and handlers for mock mode (F6): your own needs, offers and skills, other people's profiles, and connection
 * requests — replace with the B7 contract fixtures (tests/contract/). Typed against the generated API types.
 *
 * Mock rules worth knowing in tests:
 * - "Profile and Settings loading" (you_loading) and "… fail to load" (you_error) hit only this file's endpoints (the app itself opens).
 * - You are Ravi Kumar (1). Offers Frontend development, Maps, Dashboards; needs Mentoring, Backend development; one skill has a proof
 *   link. Edits are kept for the page load (and the name, bio, city and college show up in /api/me through `mePatch`).
 * - "Profile to fill in" (profile_empty) and "Empty": no needs, offers or skills, and a short bio, so the strength meter is low.
 * - People: Asha Raman (2, not connected, intro via Dr. Lakshmi), Priya Nair (3, request already sent), Arjun Mehta (4, connected),
 *   Dr. Kavya Subramanian (5, no mutual connection), Dr. Lakshmi Narayanan (7, connected), Nila Sundar (11, under 18 and hidden: strangers
 *   see "This profile is private" and no Message). Connection state and the rest come from PROFILE_EXTRAS in missing.ts.
 * - Connect always succeeds (201); a second request answers 409, which the hook treats as "Request sent".
 */
import { http, HttpResponse, delay, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import { currentScenario, type Scenario } from "./config";
import { author, PEOPLE } from "./fixtures";
import { INBOX_PEOPLE } from "./inbox";
import { isSignup } from "./signup";

const API = "*/api";
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });
type Info = { request: Request; params: Record<string, string | readonly string[] | undefined> };

/** Wait or fail the way the scenario says (same as handlers.ts). */
function scenario(fn: (s: Scenario, info: Info) => Response | Promise<Response>) {
  return async (info: Info): Promise<Response | undefined> => {
    if (isSignup()) return undefined; // the New member scenarios keep their own store (signup.ts)
    const s = currentScenario();
    if (s === "loading" || s === "you_loading") await delay("infinite");
    if (s === "slow3g") await delay(2000);
    if (s === "error" || s === "you_error") return envelope(500, "internal_error", "Something went wrong on our side.");
    return fn(s, info);
  };
}

const no = (s: Scenario) => s === "empty" || s === "profile_empty";

type Lists = { needs: Schemas["NeedOfferOut"][]; offers: Schemas["NeedOfferOut"][]; skills: Schemas["SkillOut"][] };
const cap = (capability: string) => ({ capability, description: "" });
const mine: Lists = {
  offers: ["frontend-dev", "maps", "data-viz"].map(cap),
  needs: ["mentoring", "backend-dev"].map(cap),
  skills: [{ capability: "frontend-dev", level: 3, proof_url: "https://github.com/ravikumar/farm-map" }, { capability: "maps", level: 2, proof_url: "" }],
};
const edited = new Set<keyof Lists>();

/** Name, bio, city and college as edited in this page load. handlers.ts spreads this into /api/me. */
export const mePatch: Partial<Schemas["MeOut"]> = {};
export const SHORT_BIO = "Student.";

const NILA = author(11, "Nila Sundar", "student", "Class 11, school robotics club", "Chennai", 1);

const PROFILE_LISTS: Record<number, Partial<Lists> & { bio?: string; college?: string }> = {
  2: { offers: ["product", "pitching"].map(cap), needs: ["marketing"].map(cap), skills: [{ capability: "ml", level: 3, proof_url: "https://github.com/asharaman/kannada-asr" }], bio: "Building a Kannada voice assistant for farmers who don't read English. Two years in speech models before this." },
  3: { offers: ["operations", "hiring"].map(cap), needs: ["fundraising"].map(cap), bio: "Co-founder of Aravind Pathology. Stock software for pharmacies." },
  4: { offers: ["hiring", "mentoring"].map(cap), needs: ["frontend-dev"].map(cap), bio: "Founder at Aravind Pathology. We help pharmacies in Adyar and Velachery keep stock." },
  5: { offers: ["ml"].map(cap), needs: ["marketing", "sales"].map(cap), bio: "Biotech founder. We make assay kits for small diagnostic labs." },
  7: { offers: ["sales", "mentoring", "partnerships"].map(cap), needs: ["ml"].map(cap), skills: [{ capability: "sales", level: 4, proof_url: "" }], bio: "Twenty years selling deep tech to hospitals and labs. I mentor founders with long sales cycles." },
  11: { offers: ["mobile-dev"].map(cap), needs: ["mentoring"].map(cap), bio: "Class 11. I build apps for our school robotics club.", college: "Kendriya Vidyalaya, Adyar" },
};

const everyone = [...Object.values(PEOPLE), ...Object.values(INBOX_PEOPLE), NILA];
const requested = new Set<number>([PEOPLE.priya.id]);

const listHandlers = (name: keyof Lists): HttpHandler[] => [
  http.get(`${API}/me/${name}`, scenario((s) => HttpResponse.json(no(s) && !edited.has(name) ? [] : mine[name]))),
  http.put(`${API}/me/${name}`, scenario(async (_s, { request }) => {
    const body = (await request.json()) as Array<Record<string, unknown>>;
    if (name === "skills") mine.skills = body.map((x) => ({ capability: String(x.capability), level: Number(x.level ?? 1), proof_url: String(x.proof_url ?? "") }));
    else mine[name] = body.map((x) => ({ capability: String(x.capability), description: String(x.description ?? "") }));
    edited.add(name);
    return HttpResponse.json(mine[name]);
  })),
];

/** Answered before signup.ts's handlers (which accept these PUTs in every scenario), and step aside in the New member scenarios. */
export const profileFirstHandlers: HttpHandler[] = [...listHandlers("needs"), ...listHandlers("offers"), ...listHandlers("skills")];

export const profileHandlers: HttpHandler[] = [
  http.post(`${API}/me/verify/work-email`, scenario(async (_s, { request }) => {
    const { email } = (await request.json()) as { email: string };
    if (/@(gmail|yahoo|outlook|hotmail|proton)\./i.test(email)) return envelope(422, "personal_email", "Use your work email, not a personal one.");
    return HttpResponse.json({ sent: true, dev_code: "123456" });
  })),
  http.post(`${API}/me/verify/work-email/confirm`, scenario(async (_s, { request }) => {
    const { code } = (await request.json()) as { code: string };
    if (code !== "123456") return envelope(400, "wrong_code", "That code isn't right. Check it and try again.");
    mePatch.verification_level = 2;
    return HttpResponse.json({ ok: true });
  })),
  http.patch(`${API}/me`, scenario(async (_s, { request }) => {
    const b = (await request.json()) as Schemas["MePatch"];
    for (const [k, v] of Object.entries(b)) if (v !== null && v !== undefined) (mePatch as Record<string, unknown>)[k] = v;
    return HttpResponse.json({ ok: true });
  })),
  http.get(`${API}/members/:id`, scenario((_s, { params }) => {
    const a = everyone.find((x) => x.id === Number(params.id));
    if (!a) return envelope(404, "not_found", "Not found");
    const l = PROFILE_LISTS[a.id] ?? {};
    const profile: Schemas["ProfileOut"] = {
      id: a.id, role: a.role, display_name: a.display_name, bio: l.bio ?? a.headline, city: a.city, college: l.college ?? "", verification_level: a.verification_level,
      needs: l.needs ?? [], offers: l.offers ?? [], skills: l.skills ?? [], traits: [],
      actions: { connect: true, intro: true, message: true }, build_logs: [], circuits_closed: null, circuits_together: null, connection: "none", headline: a.headline, highlights: [],
      is_me: false, mutual_count: null, organisation: null, photo: null, strength: null, via: null,
    };
    return HttpResponse.json(profile);
  })),
  http.post(`${API}/connections/requests`, scenario(async (_s, { request }) => {
    const b = (await request.json()) as Schemas["ConnectionRequestIn"];
    const other = everyone.find((x) => x.id === b.member_id);
    if (!other) return envelope(404, "not_found", "Not found");
    if (requested.has(other.id)) return envelope(409, "already_requested", "You already asked");
    requested.add(other.id);
    const out: Schemas["ConnectionRequestOut"] = { id: 800 + other.id, sender: PEOPLE.me, recipient: other, note: b.note ?? "", status: "pending", created_at: new Date().toISOString() };
    return HttpResponse.json(out, { status: 201 });
  })),
];
