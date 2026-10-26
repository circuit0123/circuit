"use client";

import { useQuery } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { kindLabel, kmText, roleLabel, rupees, sectorLabel, skillFit } from "@/lib/format";
import { api, unwrap } from "./client";
import { useFeatures } from "./features";
import { useKey } from "./keys";
import { useMe, type Me } from "./me";
import { PROMOTED_STAND_IN, PROMOTED_STARTUP_STAND_IN, type MissingJobFields } from "./missing";
import { MOCK } from "./mocks/config";
import { useCities } from "./where";

export type Segment = "people" | "startups" | "jobs" | "map";
export const SEGMENTS: { id: Segment; label: string }[] = [
  { id: "people", label: "People" },
  { id: "startups", label: "Startups" },
  { id: "jobs", label: "Jobs" },
  { id: "map", label: "Map" },
];

/** One set of filters for all four segments; each segment uses the ones the API (or the list it already has) can answer. */
export type DiscoverFilters = {
  /** Within this many km. Null = anywhere in the city. */
  distanceKm: number | null;
  capability: string | null;
  role: "student" | "founder" | "mentor" | "investor" | null;
  verifiedOnly: boolean;
  hiringOnly: boolean;
  kind: "internship" | "full_time" | "part_time" | null;
};
export const NO_FILTERS: DiscoverFilters = { distanceKm: null, capability: null, role: null, verifiedOnly: false, hiringOnly: false, kind: null };

/** Which filters each segment offers in the sheet. People can only be filtered on what /api/matches returns (see PROGRESS.md "API needed"). */
export const FILTERS_FOR: Record<Segment, Array<keyof DiscoverFilters>> = {
  people: ["role", "verifiedOnly"],
  startups: ["distanceKm", "capability", "hiringOnly", "verifiedOnly"],
  jobs: ["distanceKm", "capability", "kind"],
  map: ["capability", "hiringOnly", "distanceKm"],
};
export const activeFilters = (f: DiscoverFilters, seg: Segment) =>
  FILTERS_FOR[seg].filter((k) => f[k] !== NO_FILTERS[k]).length;

/** The pilot city's centre, only until `GET /api/cities` answers. */
const PILOT_CENTRE = { lat: 13.08, lng: 80.27 };

/** Where "near you" is measured from: the member's saved location, else the pilot city's centre. */
export function useHere(): { lat: number; lng: number } {
  const loc = useMe().data?.location;
  const pilot = useCities().data?.find((c) => c.pilot);
  return loc ?? (pilot ? { lat: pilot.lat, lng: pilot.lng } : PILOT_CENTRE);
}

export type PersonTile = { id: number; name: string; line: string; fit: string | null; bridge: boolean; level: number };

/** Discover → People: the member's matches as photo-first tiles, matched on skills. Role and "verified only" filter what came back. */
export function useDiscoverPeople(filters: DiscoverFilters, on = true) {
  const { key, enabled } = useKey("discover-people");
  const q = useQuery({
    queryKey: key,
    enabled: enabled && on,
    queryFn: async () => (await unwrap(api.GET("/api/matches", { params: { query: { limit: 40 } } }))).items,
  });
  const items: PersonTile[] = (q.data ?? [])
    .filter((m) => (!filters.role || m.role === filters.role) && (!filters.verifiedOnly || m.verification_level >= 2))
    .map((m) => ({
      id: m.candidate_id,
      name: m.display_name,
      line: m.sector ? `${roleLabel(m.role)}, ${sectorLabel(m.sector).toLowerCase()}` : roleLabel(m.role),
      fit: m.is_bridge ? "Bridge match" : m.strength === "strong" ? "Strong match" : m.strength === "good" ? "Good match" : null,
      bridge: m.is_bridge,
      level: m.verification_level,
    }));
  return { items, isPending: q.isPending && on, isError: q.isError, refetch: q.refetch };
}

export type StartupTile = { id: number; name: string; sector: string; km: number | null; hiring: boolean; openRoles: number; fit: string | null; verified: boolean };

export const toStartupTile = (p: Schemas["PinOut"]): StartupTile => ({
  id: p.id,
  name: p.name,
  sector: sectorLabel(p.sector),
  km: p.distance_km ?? null,
  hiring: p.hiring,
  openRoles: p.open_roles,
  fit: p.match_pct == null ? null : p.match_pct >= 75 ? "Strong match" : p.match_pct >= 55 ? "Good match" : null,
  verified: p.claimed,
});

/** Discover → Startups: nearby startups, closest first. */
export function useDiscoverStartups(filters: DiscoverFilters, on = true) {
  const here = useHere();
  const { key, enabled } = useKey("discover-startups", here.lat, here.lng, filters.distanceKm, filters.capability, filters.hiringOnly);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && on,
    queryFn: () => unwrap(api.GET("/api/startups/nearby", { params: { query: {
      lat: here.lat, lng: here.lng, radius_km: filters.distanceKm ?? 25, hiring: filters.hiringOnly || undefined, capability: filters.capability ?? undefined, limit: 40,
    } } })),
  });
  const items = (q.data ?? []).map(toStartupTile).filter((s) => !filters.verifiedOnly || s.verified);
  return { items, isPending: q.isPending && on, isError: q.isError, refetch: q.refetch };
}

export type JobRow = {
  id: number; title: string; startup: string; startupId: number; sector: string; km: number | null; stipend: string | null; kind: string;
  fit: string | null; applied: boolean; verified: boolean;
};

type JobIn = Schemas["JobOut"] & MissingJobFields;
export const toJobRow = (j: JobIn): JobRow => ({
  id: j.id,
  title: j.title,
  startup: j.startup_name,
  startupId: j.startup_id,
  sector: sectorLabel(j.sector),
  km: j.distance_km ?? null,
  stipend: rupees(j.stipend_min, j.stipend_max),
  kind: kindLabel(j.kind),
  fit: skillFit(j.skill_match),
  applied: !!j.applied,
  verified: j.startup_verified === true,
});

/** Under-18 members only see roles from verified startups (CLAUDE.md F19, DESIGN.md §8). A role that doesn't say counts as unverified. */
export const visibleTo = (me: Me | undefined) => (j: JobRow) => !me?.isMinor || j.verified;

/** "3.2 km" or nothing, for the one-line meta under a title: "Tatvagrid · Agritech · 3.2 km". */
export const metaLine = (...parts: Array<string | null | undefined>) => parts.filter(Boolean).join(" · ");
export const kmOrNull = (km: number | null) => (km === null ? null : kmText(km));

/** Discover → Jobs: roles that fit your skills, best fit first, then closest. */
export function useDiscoverJobs(filters: DiscoverFilters, on = true) {
  const me = useMe().data;
  const { key, enabled } = useKey("discover-jobs", filters.distanceKm, filters.capability, filters.kind);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && on,
    queryFn: async () => (await unwrap(api.GET("/api/jobs", { params: { query: {
      limit: 50, max_distance_km: filters.distanceKm ?? undefined, capability: filters.capability ?? undefined, kind: filters.kind ?? undefined,
    } } }))).items as JobIn[],
  });
  const rank = (j: JobIn) => (j.skill_match ?? 0) * 100 - (j.distance_km ?? 50) / 10;
  const items = [...(q.data ?? [])].sort((a, b) => rank(b) - rank(a)).map(toJobRow).filter(visibleTo(me));
  return { items, isPending: q.isPending && on, isError: q.isError, refetch: q.refetch };
}

/**
 * "Skills in demand near you": the capabilities the most open roles within 10 km ask for, from the jobs list itself (no endpoint of
 * its own). One sentence, as in Discover.dc.html, or null when there are too few roles to say anything.
 */
export function useSkillsInDemand(on = true) {
  const { key, enabled } = useKey("skills-in-demand");
  const q = useQuery({
    queryKey: key,
    enabled: enabled && on,
    queryFn: async () => (await unwrap(api.GET("/api/jobs", { params: { query: { limit: 100, max_distance_km: 10 } } }))).items,
  });
  const counts = new Map<string, number>();
  for (const j of q.data ?? []) for (const c of j.capabilities) if (c.required) counts.set(c.name, (counts.get(c.name) ?? 0) + 1);
  const top = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, 3).map(([n]) => n);
  const lower = (n: string) => (/^[A-Z]{2}/.test(n) ? n : n[0].toLowerCase() + n.slice(1));
  const names = top.map((n, i) => (i === 0 ? n : lower(n)));
  const text = names.length === 0 ? null
    : names.length === 1 ? `${names[0]} has the most open roles within 10 km.`
    : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]} have the most open roles within 10 km.`;
  return { text, isPending: q.isPending && on, isError: q.isError };
}

/** Search across all four segments (the map's pins are the startups), over what the lists already hold. See PROGRESS.md "API needed". */
export function useDiscoverSearch(query: string) {
  const q = query.trim().toLowerCase();
  const on = q.length > 0;
  const people = useDiscoverPeople(NO_FILTERS, on);
  const startups = useDiscoverStartups(NO_FILTERS, on);
  const jobs = useDiscoverJobs(NO_FILTERS, on);
  const has = (...s: string[]) => s.some((x) => x.toLowerCase().includes(q));
  return {
    on,
    isPending: people.isPending || startups.isPending || jobs.isPending,
    isError: people.isError && startups.isError && jobs.isError,
    people: people.items.filter((p) => has(p.name, p.line)),
    startups: startups.items.filter((s) => has(s.name, s.sector)),
    jobs: jobs.items.filter((j) => has(j.title, j.startup, j.sector)),
  };
}

export type Promotion = { key: string; why: string; label: string } & (
  | { kind: "role"; job: JobRow }
  | { kind: "startup"; startup: StartupTile }
);

/**
 * The one promoted slot at the top of Discover → Startups and Jobs (DESIGN.md §4 "Promoted items"), only with `promotions` on. The API
 * sends no promoted items yet, so mock mode shows the marked stand-ins and a real build none. Under-18 members only see promotions
 * from verified startups.
 */
export function usePromotion(seg: "startups" | "jobs"): Promotion | null {
  const features = useFeatures();
  const me = useMe().data;
  if (!MOCK || !features.raw("promotions")) return null;
  if (seg === "jobs") {
    if (me?.isMinor && !PROMOTED_STAND_IN.verified) return null;
    const r = PROMOTED_STAND_IN.role;
    return {
      key: PROMOTED_STAND_IN.key, why: PROMOTED_STAND_IN.why, label: PROMOTED_STAND_IN.startup, kind: "role",
      job: { id: r.id, title: r.title, startup: r.startup, startupId: 43, sector: "Logistics", km: r.km, stipend: r.stipend, kind: "Internship", fit: null, applied: false, verified: PROMOTED_STAND_IN.verified },
    };
  }
  const s = PROMOTED_STARTUP_STAND_IN;
  if (me?.isMinor && !s.verified) return null;
  return {
    key: s.key, why: s.why, label: s.name, kind: "startup",
    startup: { id: s.id, name: s.name, sector: sectorLabel(s.sector), km: 7.4, hiring: true, openRoles: 2, fit: null, verified: s.verified },
  };
}
