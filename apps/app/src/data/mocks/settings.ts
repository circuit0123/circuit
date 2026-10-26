/**
 * TEMPORARY settings fixtures and handlers for mock mode (F6): the one-call settings screen, privacy, notifications, blocks, data export,
 * account deletion and support — replace with the B7 contract fixtures (tests/contract/). Typed against the generated API types.
 *
 * Mock rules worth knowing in tests:
 * - "Profile and Settings loading" (you_loading) and "… fail to load" (you_error) hit only this file's endpoints (the app itself opens).
 * - Privacy starts at Members, visible to your organisation off, circuits on, requests from strangers on. Ravi is verification level 1,
 *   so turning circuits on again answers 403 (needs level 2). Under 18: Hidden, requests off; asking for Everyone or requests is 403
 *   `under_18_restricted`.
 * - Notifications: everything in the app; email only for intros and messages.
 * - Blocked: Karthik Selvam (31). Blocking someone from their profile adds them here.
 * - Export: none yet; asking makes it "preparing" (it stays so). "Data export ready" (export_ready) starts with a ready one.
 *   The email link /settings/export?token=mock-ok gives a download; token=old is expired (410); any other token is someone else's (404).
 * - Delete: the confirm word must be DELETE (422 otherwise); then 202.
 * - Support: any message gets reference CIR-2026-0042.
 */
import { http, HttpResponse, delay, type HttpHandler } from "msw";
import type { Schemas } from "@circuit/api-client";
import { currentScenario, type Scenario } from "./config";
import { author } from "./fixtures";

const API = "*/api";
const envelope = (status: number, code: string, message: string) => HttpResponse.json({ error: { code, message, details: null } }, { status });
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

type Prefs = Schemas["NotificationPrefsOut"];
const both = (email: boolean) => ({ in_app: true, email });
const prefs: Prefs = { intros: both(true), messages: both(true), applications: both(false), circuits: both(false), pulse_replies: both(false), announcements: both(false) };

let privacy: Schemas["PrivacyOut"] = { profile_visibility: "members", visible_to_org: false, circuits_opt_in: true, allow_requests: true };
const minorPrivacy = (): Schemas["PrivacyOut"] => ({ ...privacy, profile_visibility: privacy.profile_visibility === "public" ? "hidden" : privacy.profile_visibility === "members" ? "hidden" : privacy.profile_visibility, allow_requests: false });
let blocked: Schemas["PersonOut"][] = [{ id: 31, display_name: "Karthik Selvam", role: "student", verification_level: 1 }];
let exported: Schemas["ExportStatus"] | null = null;

const days = (n: number) => new Date(Date.now() + n * 86_400_000).toISOString();
const exportOf = (s: Scenario): Schemas["ExportStatus"] | null =>
  exported ?? (s === "export_ready" ? { status: "ready", requested_at: days(-1), ready_at: days(-0.9), expires_at: days(6) } : null);

const SUPPORT: Schemas["SupportOut"] = {
  support_email: "help@circuit.example",
  grievance: { name: "Grievance Officer, Circuit", email: "grievance@circuit.example", address: "Address to be published before launch" },
};

/** Privacy as the member sees it now (handlers.ts puts it into /api/me too). */
export const privacyFor = (s: Scenario) => (s === "under18" ? minorPrivacy() : privacy);

/** `me` is handlers.ts's /api/me for the scenario, so the summary, appearance and consent match what the rest of the app shows. */
export const settingsHandlers = (me: (s: Scenario) => Schemas["MeOut"]): HttpHandler[] => [
  http.get(`${API}/me/settings`, scenario((s) => {
    const m = me(s);
    const out: Schemas["SettingsOut"] = {
      profile: { display_name: m.display_name, role: m.role, city: m.city, college: m.college, is_minor: m.is_minor, verification_level: m.verification_level, email_hint: "r•••@gmail.com" },
      privacy: privacyFor(s),
      appearance: m.appearance,
      notifications: prefs,
      blocked_count: blocked.length,
      export: exportOf(s),
      consent: { policy_version: m.policy_version, accepted_version: m.policy_version, accepted_at: days(-30), needs_consent: false },
      support: SUPPORT,
    };
    return HttpResponse.json(out);
  })),
  http.patch(`${API}/me/privacy`, scenario(async (s, { request }) => {
    const b = (await request.json()) as Schemas["PrivacyPatch"];
    if (s === "under18" && (b.profile_visibility === "public" || b.allow_requests === true)) return envelope(403, "under_18_restricted", "Not available for members under 18");
    if (b.circuits_opt_in === true && me(s).verification_level < 2) return envelope(403, "verification_required", "Verify your work email to join circuits");
    privacy = { ...privacy, ...Object.fromEntries(Object.entries(b).filter(([, v]) => v !== null && v !== undefined)) };
    return HttpResponse.json(privacyFor(s));
  })),
  http.patch(`${API}/me/notification-preferences`, scenario(async (_s, { request }) => {
    const b = (await request.json()) as Schemas["NotificationPrefsPatch"];
    for (const [type, ch] of Object.entries(b)) if (ch && type in prefs) Object.assign(prefs[type as keyof Prefs], Object.fromEntries(Object.entries(ch).filter(([, v]) => typeof v === "boolean")));
    return HttpResponse.json(prefs);
  })),
  http.get(`${API}/me/blocks`, scenario((s) => HttpResponse.json({ items: s === "empty" ? [] : blocked }))),
  http.post(`${API}/members/:id/block`, scenario((_s, { params }) => {
    const id = Number(params.id);
    if (!blocked.some((p) => p.id === id)) blocked = [...blocked, { ...author(id, `Member ${id}`, "student", ""), display_name: `Member ${id}` }];
    return new HttpResponse(null, { status: 204 });
  })),
  http.delete(`${API}/members/:id/block`, scenario((_s, { params }) => {
    blocked = blocked.filter((p) => p.id !== Number(params.id));
    return new HttpResponse(null, { status: 204 });
  })),
  http.get(`${API}/me/export/download`, scenario((_s, { request }) => {
    const token = new URL(request.url).searchParams.get("token");
    if (token === "old") return envelope(410, "export_expired", "This link has expired");
    if (token !== "mock-ok") return envelope(404, "not_found", "Not found");
    return HttpResponse.json({ url: `data:application/json,${encodeURIComponent(JSON.stringify({ member: "Ravi Kumar", note: "Mock export" }))}`, expires_in: 300, size_bytes: 48_213 });
  })),
  http.get(`${API}/me/export`, scenario((s) => HttpResponse.json(exportOf(s)))),
  http.post(`${API}/me/export`, scenario(() => {
    exported = { status: "pending", requested_at: new Date().toISOString(), ready_at: null, expires_at: null };
    return HttpResponse.json(exported, { status: 202 });
  })),
  http.post(`${API}/me/deletion`, scenario(async (_s, { request }) => {
    const b = (await request.json()) as { confirm?: string };
    if (b.confirm !== "DELETE") return envelope(422, "invalid", "Type DELETE to confirm");
    return HttpResponse.json({ status: "scheduled", requested_at: new Date().toISOString() }, { status: 202 });
  })),
  http.post(`${API}/support`, scenario(() => HttpResponse.json({ reference: "CIR-2026-0042" }, { status: 202 }))),
  http.get(`${API}/support/contact`, scenario(() => HttpResponse.json(SUPPORT))),
];
