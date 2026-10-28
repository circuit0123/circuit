/**
 * TEMPORARY Discover fixtures and handlers for mock mode (F4): jobs, startups, map pins, applications, applicants, follows and the claim
 * flow — replace with the B7 contract fixtures (tests/contract/). Typed against the generated API types, plus the fields marked in
 * `missing.ts` that the API does not send yet.
 *
 * Mock rules worth knowing in tests: Sutragrid (43) and Medisetu (44) are unclaimed (so under-18 members never see Sutragrid's role);
 * Medisetu can be claimed with any address @medisetu.in and the code K7M2P9QX; in the Founder scenario the signed-in member is on Aravind
 * Pathology's team (41) and sees the applicants for its Frontend intern role (301).
 */
import { delay, http, HttpResponse, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import type { MissingJobFields } from "../missing";
import { currentScenario, type Scenario } from "./config";
import { MATCHES, ME } from "./fixtures";

const API = "*/api";
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });
const hoursAgo = (h: number) => new Date(Date.now() - h * 3600_000).toISOString();

/** Great-circle distance in km, rounded to 0.1 (what the API does with PostGIS). */
function km(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const r = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(r(b.lat - a.lat) / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lng - a.lng) / 2) ** 2;
  return Math.round(12742 * Math.asin(Math.sqrt(h)) * 10) / 10;
}
const HOME = { lat: ME.lat, lng: ME.lng };

type Startup = Omit<Schemas["StartupOut"], "interested" | "is_team" | "match_pct" | "open_jobs" | "hiring" | "build_logs" | "founders" | "logo" | "team_size" | "verified"> & { lat: number; lng: number; match_pct: number | null; careers_url?: string; hiring?: boolean };

export const STARTUPS: Startup[] = [
  { id: 41, name: "Aravind Pathology", website_domain: "aravindpath.in", description: "Stock and reorder software for neighbourhood pharmacies and pathology labs in Adyar and Velachery. Pharmacists check it before they open.", sector: "healthtech", stage: "seed", address: "Gandhi Nagar, Adyar, Chennai", lat: 13.0067, lng: 80.2573, claimed: true, source: "user", tech_stack: ["React", "Django", "PostgreSQL"], view_count: 214, interest_count: 18, match_pct: 82 },
  { id: 42, name: "Tatvagrid", website_domain: "tatvagrid.in", description: "Soil and water readings for small farms around Kanchipuram, turned into one plain message a day in Tamil.", sector: "agritech", stage: "pre_seed", address: "Tidel Park, Taramani, Chennai", lat: 12.9894, lng: 80.2486, claimed: true, source: "user", tech_stack: ["React Native", "Python", "LoRa"], view_count: 96, interest_count: 7, match_pct: 76 },
  { id: 43, name: "Sutragrid", website_domain: "sutragrid.com", description: "Route planning for small kirana distributors in north Chennai.", sector: "logistics", stage: "seed", address: "Ambattur Industrial Estate, Chennai", lat: 13.1143, lng: 80.1548, claimed: false, source: "crawler", tech_stack: ["Go", "PostgreSQL"], view_count: 41, interest_count: 3, match_pct: 61 },
  { id: 44, name: "Medisetu", website_domain: "medisetu.in", description: "Appointment and report delivery for diagnostic centres in tier 2 towns.", sector: "healthtech", stage: "idea", address: "T. Nagar, Chennai", lat: 13.0418, lng: 80.2341, claimed: false, source: "crawler", tech_stack: [], view_count: 23, interest_count: 6, match_pct: 58 },
  { id: 45, name: "Kalam Labs", website_domain: "kalamlabs.in", description: "Science kits and weekend workshops for government school students.", sector: "edtech", stage: "seed", address: "Mylapore, Chennai", lat: 13.0339, lng: 80.2619, claimed: true, source: "user", tech_stack: ["Next.js", "Firebase"], view_count: 77, interest_count: 9, match_pct: null },
  { id: 46, name: "Zetapulse", website_domain: "zetapulse.io", description: "Low-power vibration sensors for pumps in textile mills.", sector: "deeptech", stage: "pre_seed", address: "Guindy Industrial Estate, Chennai", lat: 13.0108, lng: 80.2125, claimed: true, source: "user", tech_stack: ["C", "Rust", "STM32"], view_count: 58, interest_count: 4, match_pct: 67 },
  { id: 47, name: "Neerflow", website_domain: "neerflow.in", description: "Rainwater harvesting audits for apartment associations.", sector: "climate", stage: "idea", address: "Velachery, Chennai", lat: 12.9791, lng: 80.2209, claimed: true, source: "user", tech_stack: ["Flutter"], view_count: 31, interest_count: 2, match_pct: null },
  { id: 48, name: "Ledgerly", website_domain: "ledgerly.in", description: "Bookkeeping and GST filing for small traders in Chennai. Hires through its own careers page.", sector: "fintech", stage: "seed", address: "Anna Nagar, Chennai", lat: 13.0850, lng: 80.2101, claimed: true, source: "user", tech_stack: ["Python", "React"], view_count: 52, interest_count: 5, match_pct: 64, hiring: true, careers_url: "https://ledgerly.in/careers" },
];

type Job = Schemas["JobOut"];
const cap = (slug: string, name: string, required: boolean, your_level: number | null) => ({ slug, name, required, your_level });
const job = (id: number, s: Startup, title: string, kind: string, min: number | null, max: number | null, match: number | null, description: string, caps: Schemas["JobCapabilityOut"][], hours: number): Job => ({
  id, title, description, kind, is_open: true, sector: s.sector, startup_id: s.id, startup_name: s.name, location: s.address.split(",").slice(-2).join(",").trim(),
  lat: s.lat, lng: s.lng, distance_km: km(HOME, s), stipend_min: min, stipend_max: max, skill_match: match, applied: false, contact: null, duration_weeks: null, is_team: false, starts_on: null, startup_logo: null, created_at: hoursAgo(hours), capabilities: caps,
  startup_verified: s.claimed,
});

const by = (id: number) => STARTUPS.find((s) => s.id === id)!;
export const JOBS: Job[] = [
  job(301, by(41), "Frontend intern", "internship", 12000, 15000, 0.82, "You'll own the stock and reorder screens pharmacists use every morning: fast on cheap phones, clear in a busy shop, and right about every rupee.", [cap("frontend-dev", "Frontend development", true, 3), cap("ui-design", "UI design", true, 2), cap("data-viz", "Dashboards", true, 2), cap("backend-dev", "Backend development", false, null)], 30),
  job(302, by(42), "Mobile app intern", "internship", 15000, 15000, 0.76, "Build the Tamil-first app farmers open once a day. Offline first, big type, and one clear message.", [cap("mobile-dev", "Mobile apps", true, 2), cap("frontend-dev", "Frontend development", true, 3), cap("maps", "Maps", false, null)], 50),
  job(303, by(42), "Data analyst intern", "internship", 10000, 12000, 0.58, "Turn sensor readings from 300 farms into the one number each farmer needs.", [cap("data-analysis", "Data analysis", true, 1), cap("data-viz", "Dashboards", true, 2)], 70),
  job(304, by(43), "Backend engineer intern", "internship", 15000, 18000, 0.61, "Help route 40 delivery vans a day across north Chennai.", [cap("backend-dev", "Backend development", true, null), cap("devops", "DevOps", false, null)], 90),
  job(305, by(46), "Embedded intern", "internship", 12000, 12000, null, "Write firmware for vibration sensors that run a year on one battery.", [cap("devops", "DevOps", true, null)], 120),
];

/** What the mock remembers in this page load. */
const applied = new Map<number, { id: number; status: string; created_at: string }>([[305, { id: 9001, status: "shortlisted", created_at: hoursAgo(72) }]]);
const followed = new Set<number>([45]);
const interestedIn = new Set<number>([42]);
const claimedNow = new Set<number>();
const applicantStatus = new Map<number, string>();

const founder = (s: Scenario) => s === "founder";
const isTeam = (s: Scenario, id: number) => (founder(s) && id === 41) || claimedNow.has(id);
const empty = (s: Scenario) => s === "empty";

const jobOut = (j: Job): Job => ({ ...j, applied: applied.has(j.id) });
const openJobs = (id: number) => JOBS.filter((j) => j.startup_id === id);
const hiring = (s: Startup) => s.hiring ?? openJobs(s.id).length > 0;
/** Like the API: to an under-18 an unverified startup has no hiring, roles or careers page. */
const hidden = (s: Startup, sc: Scenario) => sc === "under18" && !s.claimed;

function startupOut(s: Startup, sc: Scenario): Schemas["StartupOut"] {
  return {
    ...s,
    claimed: s.claimed || claimedNow.has(s.id),
    hiring: hiring(s) && !hidden(s, sc),
    careers_url: hidden(s, sc) ? null : s.careers_url ?? null,
    interested: interestedIn.has(s.id),
    build_logs: [],
    founders: [],
    logo: null,
    team_size: null,
    verified: s.claimed,
    is_team: isTeam(sc, s.id),
    open_jobs: hidden(s, sc) ? [] : openJobs(s.id).map((j) => ({ id: j.id, title: j.title, kind: j.kind, stipend_min: j.stipend_min, stipend_max: j.stipend_max })),
  };
}

const pinOut = (s: Startup, sc: Scenario): Schemas["PinOut"] => ({
  id: s.id, name: s.name, sector: s.sector, lat: s.lat, lng: s.lng, hiring: hiring(s) && !hidden(s, sc), open_roles: hidden(s, sc) ? 0 : openJobs(s.id).length, careers_url: hidden(s, sc) ? null : s.careers_url ?? null,
  claimed: s.claimed || claimedNow.has(s.id), distance_km: km(HOME, s), match_pct: s.match_pct,
});
const hasCapability = (s: Startup, slug: string | null) => !slug || openJobs(s.id).some((j) => j.capabilities.some((c) => c.slug === slug));

function applicationOut(jobId: number): Schemas["ApplicationOut"] {
  const j = JOBS.find((x) => x.id === jobId)!;
  const a = applied.get(jobId)!;
  return { id: a.id, job_id: j.id, job_title: j.title, startup_id: j.startup_id, startup_name: j.startup_name, status: a.status, skill_match: j.skill_match ?? 0, created_at: a.created_at };
}

const skill = (capability: string, level: number, proof_url = "") => ({ capability, name: capability, level, proof_url });
const APPLICANTS: Schemas["ApplicantOut"][] = [
  { application_id: 7001, student_id: 21, display_name: "Karthik Selvam", skill_match: 0.91, status: "submitted", applied_at: hoursAgo(5), skills: [skill("frontend-dev", 3, "https://github.com/karthik-selvam/ration-tracker"), skill("ui-design", 2), skill("data-viz", 3, "https://karthik.dev/dashboards")] },
  { application_id: 7002, student_id: 22, display_name: "Fathima Rizwana", skill_match: 0.78, status: "shortlisted", applied_at: hoursAgo(20), skills: [skill("frontend-dev", 2, "https://github.com/fathimarizwana"), skill("ui-design", 3)] },
  { application_id: 7003, student_id: 23, display_name: "Arun Prakash", skill_match: 0.63, status: "submitted", applied_at: hoursAgo(26), skills: [skill("frontend-dev", 2), skill("data-viz", 1)] },
  { application_id: 7004, student_id: 24, display_name: "Deepika Rao", skill_match: 0.4, status: "submitted", applied_at: hoursAgo(40), skills: [skill("backend-dev", 2)] },
];

/** Wait or fail the way the scenario says (same as handlers.ts). */
function scenario(fn: (s: Scenario, info: { request: Request; params: Record<string, string | readonly string[] | undefined> }) => Response | Promise<Response>) {
  return async (info: { request: Request; params: Record<string, string | readonly string[] | undefined> }): Promise<Response> => {
    const s = currentScenario();
    // The two Discover scenarios fail or hang only Discover's own calls, so the screen's states show inside a working app.
    if (s === "loading" || s === "discover_loading") await delay("infinite");
    if (s === "slow3g") await delay(2000);
    if (s === "error" || s === "discover_error") return envelope(500, "internal_error", "Something went wrong on our side.");
    return fn(s, info);
  };
}
const num = (q: URLSearchParams, k: string) => (q.get(k) === null || q.get(k) === "" ? null : Number(q.get(k)));

export const discoverHandlers: HttpHandler[] = [
  http.get(`${API}/jobs/skills-in-demand`, scenario((s) => {
    const counts = new Map<string, { slug: string; name: string; open_roles: number }>();
    for (const j of empty(s) ? [] : JOBS) for (const c of j.capabilities) if (c.required && (j.distance_km ?? Infinity) <= 10) counts.set(c.slug, { slug: c.slug, name: c.name, open_roles: (counts.get(c.slug)?.open_roles ?? 0) + 1 });
    const skills = [...counts.values()].sort((a, b) => b.open_roles - a.open_roles || a.name.localeCompare(b.name)).slice(0, 3);
    return HttpResponse.json(skills);
  })),
  http.get(`${API}/search`, scenario((s, { request }) => {
    const q = (new URL(request.url).searchParams.get("q") ?? "").trim().toLowerCase();
    if (q.length < 2) return envelope(422, "validation_error", "Type at least 2 characters.");
    const has = (...x: string[]) => x.some((v) => v.toLowerCase().includes(q));
    if (empty(s)) return HttpResponse.json({ people: [], startups: [], jobs: [] });
    return HttpResponse.json({
      people: MATCHES.filter((m) => has(m.display_name)).slice(0, 10).map((m) => ({ id: m.candidate_id, display_name: m.display_name, headline: m.headline ?? "", role: m.role, city: "Chennai", photo: null, verification_level: m.verification_level })),
      startups: STARTUPS.filter((x) => has(x.name, x.sector)).slice(0, 10).map((x) => pinOut(x, s)),
      jobs: JOBS.filter((j) => has(j.title, j.startup_name, j.sector)).slice(0, 10).map(jobOut),
    });
  })),
  http.get(`${API}/jobs`, scenario((s, { request }) => {
    const q = new URL(request.url).searchParams;
    const limit = num(q, "limit") ?? 20;
    const offset = num(q, "offset") ?? 0;
    const maxKm = num(q, "max_distance_km");
    const minStipend = num(q, "min_stipend");
    const all = (empty(s) ? [] : JOBS).filter((j) =>
      (!q.get("kind") || j.kind === q.get("kind")) &&
      (!q.get("capability") || j.capabilities.some((c) => c.slug === q.get("capability"))) &&
      (num(q, "startup_id") === null || j.startup_id === num(q, "startup_id")) &&
      (maxKm === null || (j.distance_km ?? Infinity) <= maxKm) &&
      (minStipend === null || (j.stipend_max ?? 0) >= minStipend)).map(jobOut);
    return HttpResponse.json({ items: all.slice(offset, offset + limit), count: all.length, next_offset: offset + limit < all.length ? offset + limit : null });
  })),
  http.get(`${API}/jobs/:id/applicants`, scenario((s, { params }) => {
    const j = JOBS.find((x) => x.id === Number(params.id));
    if (!j || !isTeam(s, j.startup_id)) return envelope(403, "forbidden", "Only the startup's team can see its applicants.");
    const items = (j.id === 301 ? APPLICANTS : []).map((a) => ({ ...a, status: applicantStatus.get(a.application_id) ?? a.status }));
    return HttpResponse.json({ items, count: items.length, next_offset: null });
  })),
  http.get(`${API}/jobs/:id`, scenario((_s, { params }) => {
    const j = JOBS.find((x) => x.id === Number(params.id));
    return j ? HttpResponse.json(jobOut(j)) : envelope(404, "not_found", "No such job.");
  })),
  http.post(`${API}/jobs/:id/apply`, scenario((s, { params }) => {
    const id = Number(params.id);
    if (!JOBS.some((j) => j.id === id)) return envelope(404, "not_found", "No such job.");
    if (founder(s)) return envelope(403, "forbidden", "Only students can apply.");
    const again = applied.has(id);
    if (!again) applied.set(id, { id: 9000 + id, status: "submitted", created_at: new Date().toISOString() });
    return HttpResponse.json(applicationOut(id), { status: again ? 200 : 201 });
  })),
  http.get(`${API}/me/applications`, scenario((s) => {
    const items = empty(s) || founder(s) ? [] : [...applied.keys()].map(applicationOut).sort((a, b) => b.created_at.localeCompare(a.created_at));
    return HttpResponse.json({ items, count: items.length, next_offset: null });
  })),
  http.patch(`${API}/applications/:id`, scenario(async (s, { params, request }) => {
    const a = APPLICANTS.find((x) => x.application_id === Number(params.id));
    if (!a || !founder(s)) return envelope(403, "forbidden", "Only the startup's team can change this.");
    const { status } = (await request.json()) as { status: string };
    applicantStatus.set(a.application_id, status);
    return HttpResponse.json({ id: a.application_id, job_id: 301, job_title: "Frontend intern", startup_id: 41, startup_name: "Aravind Pathology", status, skill_match: a.skill_match, created_at: a.applied_at });
  })),

  http.get(`${API}/startups/map`, scenario((s, { request }) => {
    const q = new URL(request.url).searchParams;
    const [w, so, e, n] = ["min_lng", "min_lat", "max_lng", "max_lat"].map((k) => Number(q.get(k)));
    if (e - w > 2 || n - so > 2) return envelope(422, "bbox_too_large", "Zoom in: that map area is too large"); // the API's MAX_BBOX_DEGREES
    const pins = (empty(s) ? [] : STARTUPS).filter((x) => x.lng >= w && x.lng <= e && x.lat >= so && x.lat <= n && (q.get("hiring") !== "true" || (hiring(x) && !hidden(x, s))) && hasCapability(x, q.get("capability"))).map((x) => pinOut(x, s));
    return HttpResponse.json(pins);
  })),
  http.get(`${API}/startups/nearby`, scenario((s, { request }) => {
    const q = new URL(request.url).searchParams;
    const radius = num(q, "radius_km") ?? 25;
    const pins = (empty(s) ? [] : STARTUPS).map((x) => pinOut(x, s)).filter((p) => (p.distance_km ?? 0) <= radius && (q.get("hiring") !== "true" || p.hiring) && hasCapability(by(p.id), q.get("capability")))
      .sort((a, b) => (a.distance_km ?? 0) - (b.distance_km ?? 0)).slice(0, num(q, "limit") ?? 20);
    return HttpResponse.json(pins);
  })),
  http.get(`${API}/startups/:id`, scenario((s, { params }) => {
    const x = STARTUPS.find((y) => y.id === Number(params.id));
    return x ? HttpResponse.json(startupOut(x, s)) : envelope(404, "not_found", "No such startup.");
  })),
  http.post(`${API}/startups/:id/follow`, scenario((_s, { params }) => { followed.add(Number(params.id)); return new HttpResponse(null, { status: 204 }); })),
  http.post(`${API}/startups/:id/interest`, scenario((_s, { params }) => { interestedIn.add(Number(params.id)); return new HttpResponse(null, { status: 204 }); })),
  http.delete(`${API}/startups/:id/interest`, scenario((_s, { params }) => { interestedIn.delete(Number(params.id)); return new HttpResponse(null, { status: 204 }); })),
  http.delete(`${API}/startups/:id/follow`, scenario((_s, { params }) => { followed.delete(Number(params.id)); return new HttpResponse(null, { status: 204 }); })),
  http.get(`${API}/me/follows`, scenario((s) => HttpResponse.json(empty(s) ? [] : STARTUPS.filter((x) => followed.has(x.id)).map((x) => ({ id: x.id, name: x.name, sector: x.sector, hiring: hiring(x) }))))),
  http.post(`${API}/startups/:id/claim`, scenario(async (_s, { params, request }) => {
    const x = STARTUPS.find((y) => y.id === Number(params.id));
    if (!x) return envelope(404, "not_found", "No such startup.");
    const { email } = (await request.json()) as { email: string };
    if (!email.toLowerCase().endsWith(`@${x.website_domain}`)) return envelope(400, "email_domain_mismatch", `Use an email address at ${x.website_domain}.`);
    return HttpResponse.json({ sent: true, dev_code: "K7M2P9QX" });
  })),
  http.post(`${API}/startups/:id/claim/verify`, scenario(async (s, { params, request }) => {
    const x = STARTUPS.find((y) => y.id === Number(params.id));
    if (!x) return envelope(404, "not_found", "No such startup.");
    const { code } = (await request.json()) as { code: string };
    if (code !== "K7M2P9QX") return envelope(400, "invalid_code", "That code is wrong or has expired.");
    claimedNow.add(x.id);
    return HttpResponse.json(startupOut(x, s));
  })),
];
