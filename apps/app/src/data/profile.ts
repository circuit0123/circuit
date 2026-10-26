"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import type { PostView } from "@circuit/ui";
import { useMemo } from "react";
import { roleLabel } from "@/lib/format";
import { useCapabilities } from "./capabilities";
import { useCircuits } from "./circuits";
import { api, ApiError, unwrap } from "./client";
import { useFeatures } from "./features";
import { useReport } from "./home";
import { useKey } from "./keys";
import { toPost } from "./mappers";
import { useMe } from "./me";
import { ME_EXTRAS, PROFILE_EXTRAS, type Connection, type Highlight } from "./missing";
import { MOCK } from "./mocks/config";

export type { Highlight };
export type ConnectionState = Connection;
export type ChipItem = { slug: string; name: string };
export type SkillItem = { slug: string; name: string; level: number; proof: string };

/** Everything a profile page draws, for your own profile and for someone else's (DESIGN.md §4 Profile). No public counts anywhere. */
export type ProfileView = {
  id: number;
  name: string;
  role: string;
  /** "Frontend developer · Chennai": headline (or role) and place. */
  line: string;
  org: string | null;
  level: number;
  bio: string;
  college: string;
  offers: ChipItem[];
  needs: ChipItem[];
  skills: SkillItem[];
  highlights: Highlight[];
  /** Null when the API can't say (no circuits tab then). */
  circuits: string[] | null;
};

export type PersonView = ProfileView & {
  minor: boolean;
  /** Under 18 and not connected: only "This profile is private" is shown. */
  hidden: boolean;
  connection: Connection;
  /** "12 mutual connections". Null when unknown. */
  mutuals: number | null;
  canMessage: boolean;
};

export type StrengthStep = { id: string; label: string; href: string };
/** The owner-only profile strength meter (DESIGN.md §4): how much is filled in, and the one next step. */
export type Strength = { percent: number; next: StrengthStep | null };

const LEVELS = ["", "Learning", "Comfortable", "Strong", "Expert"];
export const skillLevel = (n: number) => LEVELS[Math.min(Math.max(n, 1), 4)];

function useNames() {
  const caps = useCapabilities();
  return useMemo(() => new Map((caps.data ?? []).map((c) => [c.slug, c.name])), [caps.data]);
}
const chipsOf = (names: Map<string, string>, xs: Array<{ capability: string }>): ChipItem[] => xs.map((x) => ({ slug: x.capability, name: names.get(x.capability) ?? x.capability }));
const skillsOf = (names: Map<string, string>, xs: Schemas["SkillOut"][]): SkillItem[] => xs.map((x) => ({ slug: x.capability, name: names.get(x.capability) ?? x.capability, level: x.level, proof: x.proof_url }));
const lineOf = (headline: string | undefined, role: string, place: string) => [headline || roleLabel(role), place].filter(Boolean).join(" · ");

/** A member's build logs, newest first (only while the `pulse` flag is on: build logs belong to it). */
export function useMemberPosts(id: number | undefined) {
  const features = useFeatures();
  const me = useMe().data;
  const on = features.on("pulse");
  const { key, enabled } = useKey("member-posts", id);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && on && !!id,
    queryFn: () => unwrap(api.GET("/api/members/{member_id}/posts", { params: { path: { member_id: id! } } })),
  });
  const posts: PostView[] = (q.data ?? []).map((p) => toPost(p, me?.id));
  return { on, posts, isPending: on && q.isPending, isError: q.isError, refetch: q.refetch };
}

/**
 * Someone else's profile. Connection state, mutual count, under-18 privacy, highlights and shared circuits aren't in `ProfileOut` yet:
 * mock mode reads them from a marked stand-in (missing.ts), a real build leaves those parts out and the server refuses what isn't allowed.
 */
export function useProfile(id: number) {
  const names = useNames();
  const qc = useQueryClient();
  const valid = Number.isFinite(id) && id > 0;
  const { key, enabled } = useKey("profile", id);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && valid,
    queryFn: () => unwrap(api.GET("/api/members/{member_id}", { params: { path: { member_id: id } } })),
  });
  // Connect is optimistic: what the viewer did in this session wins over the stand-in.
  const { key: connKey } = useKey("connection", id);
  const sent = useQuery({ queryKey: connKey, queryFn: () => null as Connection | null, staleTime: Infinity, gcTime: Infinity }).data ?? null;
  const p = q.data;
  const x = MOCK && p ? PROFILE_EXTRAS[p.id] ?? {} : {};
  const connection: Connection = sent ?? x.connection ?? "none";
  const data: PersonView | undefined = p && {
    id: p.id,
    name: p.display_name,
    role: roleLabel(p.role),
    line: lineOf(x.headline, p.role, p.city),
    org: x.org ?? null,
    level: p.verification_level,
    bio: p.bio,
    college: p.college,
    offers: chipsOf(names, p.offers),
    needs: chipsOf(names, p.needs),
    skills: skillsOf(names, p.skills),
    highlights: x.highlights ?? [],
    circuits: MOCK ? x.circuits ?? [] : null,
    minor: x.minor ?? false,
    hidden: !!x.hidden && connection !== "connected",
    connection,
    mutuals: x.mutuals ?? null,
    canMessage: x.canMessage ?? true,
  };

  const connect = useMutation({
    mutationFn: async (note: string) => {
      try { await unwrap(api.POST("/api/connections/requests", { body: { member_id: id, note } })); }
      catch (e) { if (!(e instanceof ApiError && e.status === 409)) throw e; } // already asked (or already connected): the button says so either way
    },
    onMutate: () => { qc.setQueryData(connKey, "pending"); },
    onError: () => { qc.setQueryData(connKey, null); },
  });
  const report = useReport();
  const block = useMutation({
    mutationFn: () => unwrap(api.POST("/api/members/{member_id}/block", { params: { path: { member_id: id } } })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["inbox"] }); qc.invalidateQueries({ queryKey: ["pulse"] }); },
  });

  return {
    data,
    isPending: q.isPending,
    isError: q.isError,
    notFound: (q.error as { status?: number } | null)?.status === 404 || !valid,
    refetch: q.refetch,
    connect,
    block,
    report: (reason: string) => report.mutateAsync({ target_type: "member", target_id: id, reason }),
  };
}

/** Your own needs, offers and skills: three small lists the API keeps apart. */
function useMine() {
  const { key: needsKey, enabled } = useKey("my-needs");
  const { key: offersKey } = useKey("my-offers");
  const { key: skillsKey } = useKey("my-skills");
  const needs = useQuery({ queryKey: needsKey, enabled, queryFn: () => unwrap(api.GET("/api/me/needs")) });
  const offers = useQuery({ queryKey: offersKey, enabled, queryFn: () => unwrap(api.GET("/api/me/offers")) });
  const skills = useQuery({ queryKey: skillsKey, enabled, queryFn: () => unwrap(api.GET("/api/me/skills")) });
  return { needs, offers, skills };
}

/**
 * Your own profile (Profile.dc.html) with the owner-only strength meter. The meter is worked out here from what is filled in; there is
 * no endpoint for it. A step that needs a feature that is off (the build log needs `pulse`) isn't counted.
 */
export function useMyProfile() {
  const me = useMe();
  const names = useNames();
  const features = useFeatures();
  const mine = useMine();
  const posts = useMemberPosts(me.data?.id);
  const circuitsOn = features.on("circuits");
  const circuits = useCircuits();
  const m = me.data;
  const x = MOCK ? ME_EXTRAS : {};

  const data: (ProfileView & { minor: boolean; hiddenFromPublic: boolean }) | undefined = m && mine.needs.data && mine.offers.data && mine.skills.data ? {
    id: m.id,
    name: m.name,
    role: roleLabel(m.role),
    line: lineOf(x.headline, m.role, m.city),
    org: x.org ?? (m.college || null),
    level: m.level,
    bio: m.bio,
    college: m.college,
    offers: chipsOf(names, mine.offers.data),
    needs: chipsOf(names, mine.needs.data),
    skills: skillsOf(names, mine.skills.data),
    highlights: x.highlights ?? [],
    circuits: circuitsOn ? [...circuits.current.map((c) => (c.closed ? "Circuit closed this week" : "Circuit in progress")), ...circuits.history.map((h) => h.label)] : null,
    minor: m.isMinor,
    hiddenFromPublic: m.isMinor,
  } : undefined;

  const steps: Array<StrengthStep & { done: boolean }> = data ? [
    { id: "bio", label: "Write two lines about what you're building", href: "/settings/profile#bio", done: data.bio.trim().length >= 20 },
    { id: "offers", label: "Add what you can offer", href: "/settings/profile#offers", done: data.offers.length > 0 },
    { id: "needs", label: "Add what you need help with", href: "/settings/profile#needs", done: data.needs.length > 0 },
    { id: "skills", label: "Add a skill with a proof-of-work link", href: "/settings/profile#skills", done: data.skills.some((s) => !!s.proof) },
    ...(posts.on ? [{ id: "log", label: "Post your first build log", href: "/compose", done: posts.posts.length > 0 }] : []),
  ] : [];
  const done = steps.filter((s) => s.done).length;
  const next = steps.find((s) => !s.done);
  const strength: Strength | undefined = data && !posts.isPending ? { percent: Math.round((done / steps.length) * 100), next: next ? { id: next.id, label: next.label, href: next.href } : null } : undefined;

  return {
    data,
    strength,
    posts,
    isPending: me.isPending || mine.needs.isPending || mine.offers.isPending || mine.skills.isPending,
    isError: me.isError || mine.needs.isError || mine.offers.isError || mine.skills.isError,
    refetch: () => { me.refetch(); mine.needs.refetch(); mine.offers.refetch(); mine.skills.refetch(); },
  };
}

export type ProfileEdit = {
  name: string;
  bio: string;
  city: string;
  college: string;
  offers: string[];
  needs: string[];
  /** Slug → proof link ("" for none). */
  skills: Array<{ slug: string; proof: string }>;
};

/** What Edit profile starts from. */
export function useProfileDraft(): ProfileEdit | undefined {
  const me = useMe().data;
  const mine = useMine();
  if (!me || !mine.needs.data || !mine.offers.data || !mine.skills.data) return undefined;
  return {
    name: me.name, bio: me.bio, city: me.city, college: me.college,
    offers: mine.offers.data.map((o) => o.capability),
    needs: mine.needs.data.map((n) => n.capability),
    skills: mine.skills.data.map((s) => ({ slug: s.capability, proof: s.proof_url })),
  };
}

/** Saves Edit profile: the basics, then the three lists. Levels already set on a skill are kept. */
export function useSaveProfile() {
  const qc = useQueryClient();
  const { key: skillsKey } = useKey("my-skills");
  return useMutation({
    mutationFn: async (e: ProfileEdit) => {
      const before = qc.getQueryData<Schemas["SkillOut"][]>(skillsKey) ?? [];
      const level = (slug: string) => before.find((s) => s.capability === slug)?.level ?? 2;
      await unwrap(api.PATCH("/api/me", { body: { display_name: e.name.trim(), bio: e.bio.trim(), city: e.city.trim(), college: e.college.trim() } }));
      await Promise.all([
        unwrap(api.PUT("/api/me/offers", { body: e.offers.map((capability) => ({ capability, description: "" })) })),
        unwrap(api.PUT("/api/me/needs", { body: e.needs.map((capability) => ({ capability, description: "" })) })),
        unwrap(api.PUT("/api/me/skills", { body: e.skills.map((s) => ({ capability: s.slug, level: level(s.slug), proof_url: s.proof.trim() })) })),
      ]);
    },
    onSettled: () => {
      for (const k of ["me", "my-needs", "my-offers", "my-skills", "settings"]) qc.invalidateQueries({ queryKey: [k] });
    },
  });
}
