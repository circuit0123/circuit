"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { sectorLabel, stageLabel } from "@/lib/format";
import { api, ApiError, unwrap } from "./client";
import { toStartupTile, useHere, type DiscoverFilters, type StartupTile } from "./discover";
import { useFeatures } from "./features";
import { useKey } from "./keys";
import { useMe } from "./me";
import { STARTUP_EXTRAS, type StartupFounder, type StartupLog } from "./missing";

export type { StartupFounder, StartupLog };
import { MOCK } from "./mocks/config";

function km(a: { lat: number; lng: number }, b: { lat: number; lng: number }) {
  const r = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(r(b.lat - a.lat) / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lng - a.lng) / 2) ** 2;
  return Math.round(12742 * Math.asin(Math.sqrt(h)) * 10) / 10;
}

export type StartupPage = {
  id: number;
  name: string;
  sector: string;
  stage: string;
  place: string;
  km: number | null;
  website: string;
  about: string;
  techStack: string[];
  claimed: boolean;
  fromPublicSources: boolean;
  hiring: boolean;
  openRoles: number;
  careersUrl: string | null;
  /** The signed-in member is on this startup's team: they see its private counts and its applicants. */
  isTeam: boolean;
  /** Only for the team (DESIGN.md §4: never public). */
  privateCounts: { views: number | null; interested: number | null } | null;
  /** Shown to founders on an unclaimed page, to say why claiming is worth it (CLAUDE.md F3). */
  claimNudge: { views: number | null; interested: number | null } | null;
  canClaim: boolean;
  /** Students can tell a startup they're interested; everyone else has no such button. */
  canShowInterest: boolean;
  interested: boolean;
  teamSize: number | null;
  founders: StartupFounder[];
  logs: StartupLog[];
};

/**
 * The Startup page (DESIGN.md §4): one call for the page; distance is worked out here from the member's location. Team size, founders and
 * build logs aren't in the API yet (PROGRESS.md "API needed"): mock mode fills them from a marked stand-in, a real build leaves them out.
 */
export function useStartup(id: number) {
  const me = useMe().data;
  const here = useHere();
  const features = useFeatures();
  const { key, enabled } = useKey("startup", id);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && Number.isFinite(id),
    queryFn: () => unwrap(api.GET("/api/startups/{startup_id}", { params: { path: { startup_id: id } } })),
  });
  const s = q.data;
  const extras = MOCK && s ? STARTUP_EXTRAS[s.id] : undefined;
  const data: StartupPage | undefined = s && {
    id: s.id,
    name: s.name,
    sector: sectorLabel(s.sector),
    stage: stageLabel(s.stage),
    place: s.address,
    km: s.lat != null && s.lng != null ? km(here, { lat: s.lat, lng: s.lng }) : null,
    website: s.website_domain,
    about: s.description,
    techStack: (s.tech_stack as string[]) ?? [],
    claimed: s.claimed,
    fromPublicSources: !s.claimed && s.source !== "user",
    hiring: s.hiring,
    openRoles: s.open_jobs.length,
    careersUrl: s.careers_url ?? null,
    isTeam: s.is_team,
    privateCounts: s.is_team ? { views: s.view_count, interested: s.interest_count } : null,
    claimNudge: !s.claimed && me?.role === "founder" ? { views: s.view_count, interested: s.interest_count } : null,
    canClaim: !s.claimed && me?.role === "founder",
    canShowInterest: me?.role === "student",
    interested: s.interested,
    teamSize: extras?.teamSize ?? null,
    founders: extras?.founders ?? [],
    logs: features.on("pulse") ? extras?.logs ?? [] : [],
  };
  return { ...q, data, notFound: q.error instanceof ApiError && q.error.status === 404 };
}

/** The startups the member follows. Following is per member, so the page asks this list rather than the startup. */
export function useFollows() {
  const { key, enabled } = useKey("follows");
  return useQuery({ queryKey: key, enabled, queryFn: async () => new Set((await unwrap(api.GET("/api/me/follows"))).map((f) => f.id)) });
}

/** Follow / unfollow, shown at once and put back if the call fails. */
export function useFollow() {
  const qc = useQueryClient();
  const { key } = useKey("follows");
  return useMutation({
    mutationFn: ({ id, on }: { id: number; on: boolean }) =>
      on ? unwrap(api.POST("/api/startups/{startup_id}/follow", { params: { path: { startup_id: id } } }))
        : unwrap(api.DELETE("/api/startups/{startup_id}/follow", { params: { path: { startup_id: id } } })),
    onMutate: ({ id, on }) => {
      qc.setQueryData<Set<number>>(key, (old) => {
        const next = new Set(old ?? []);
        if (on) next.add(id); else next.delete(id);
        return next;
      });
    },
    onError: () => qc.invalidateQueries({ queryKey: key }),
  });
}

/**
 * "I'm interested" (students only): shown at once, put back if the call fails. The API has no list of startups I'm interested in, so the
 * answer lives in the cache: the Startup page seeds it from `interested`; the map popup doesn't know and starts from "no" (the call is safe to repeat).
 */
export function useInterest(id: number, seed = false) {
  const qc = useQueryClient();
  const { key, enabled } = useKey("interest", id);
  const state = useQuery({ queryKey: key, enabled, staleTime: Infinity, queryFn: async () => seed });
  const set = useMutation({
    mutationFn: (on: boolean) =>
      on ? unwrap(api.POST("/api/startups/{startup_id}/interest", { params: { path: { startup_id: id } } }))
        : unwrap(api.DELETE("/api/startups/{startup_id}/interest", { params: { path: { startup_id: id } } })),
    onMutate: (on) => { const before = qc.getQueryData<boolean>(key); qc.setQueryData(key, on); return { before }; },
    onError: (_e, _on, ctx) => qc.setQueryData(key, ctx?.before ?? false),
  });
  /** Resolves true when saved, false when it failed (and was put back). */
  const setInterested = async (on: boolean) => { try { await set.mutateAsync(on); return true; } catch { return false; } };
  return { interested: state.data ?? seed, set: setInterested, pending: set.isPending };
}

export type ClaimFailure = "wrong_domain" | "wrong_code" | "failed";
export class ClaimError extends Error {
  constructor(readonly failure: ClaimFailure, readonly detail: string) { super(detail); }
}
const claimFailure = (e: unknown, kind: "email" | "code") =>
  e instanceof ApiError && (e.status === 400 || e.status === 422)
    ? new ClaimError(kind === "email" ? "wrong_domain" : "wrong_code", e.message)
    : new ClaimError("failed", "Couldn't send that. Check your connection and try again.");

/** Claim step 1: a code to a work email on the startup's own domain (CLAUDE.md F3). Dev builds answer with the code itself. */
export function useStartClaim(id: number) {
  return useMutation({
    mutationFn: async (email: string) => {
      try { return await unwrap(api.POST("/api/startups/{startup_id}/claim", { params: { path: { startup_id: id } }, body: { email } })); }
      catch (e) { throw claimFailure(e, "email"); }
    },
  });
}

/** Claim step 2: the code. On success the page becomes the founder's (claimed data is never overwritten by the crawler). */
export function useVerifyClaim(id: number) {
  const qc = useQueryClient();
  const { key } = useKey("startup", id);
  return useMutation({
    mutationFn: async (code: string) => {
      try { return await unwrap(api.POST("/api/startups/{startup_id}/claim/verify", { params: { path: { startup_id: id } }, body: { code } })); }
      catch (e) { throw claimFailure(e, "code"); }
    },
    onSuccess: (s) => {
      qc.setQueryData<Schemas["StartupOut"]>(key, s);
      void qc.invalidateQueries({ predicate: (x) => ["discover-startups", "map-pins"].includes(String(x.queryKey[0])) });
    },
  });
}

export type Bounds = { west: number; south: number; east: number; north: number };

/** Pins in the visible part of the map. Bounds are rounded so a small pan reuses the last answer. */
export function useMapPins(bounds: Bounds | null, filters: DiscoverFilters) {
  const r = (n: number) => Math.round(n * 100) / 100;
  const b = bounds && { west: r(bounds.west) - 0.01, south: r(bounds.south) - 0.01, east: r(bounds.east) + 0.01, north: r(bounds.north) + 0.01 };
  const { key, enabled } = useKey("map-pins", b?.west, b?.south, b?.east, b?.north, filters.hiringOnly, filters.capability);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && !!b,
    placeholderData: (prev) => prev,
    queryFn: () => unwrap(api.GET("/api/startups/map", { params: { query: {
      min_lng: b!.west, min_lat: b!.south, max_lng: b!.east, max_lat: b!.north, hiring: filters.hiringOnly || undefined, capability: filters.capability ?? undefined,
    } } })),
  });
  const pins: Array<StartupTile & { lat: number; lng: number }> = (q.data ?? [])
    .map((p) => ({ ...toStartupTile(p), lat: p.lat, lng: p.lng }))
    .filter((p) => filters.distanceKm === null || (p.km !== null && p.km <= filters.distanceKm));
  const tooWide = q.error instanceof ApiError && q.error.code === "bbox_too_large"; // the server only serves a city-sized area
  return { pins, isPending: q.isPending && !!b, isError: q.isError && !tooWide, tooWide, refetch: q.refetch };
}
