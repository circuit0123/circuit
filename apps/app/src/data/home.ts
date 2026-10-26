"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { DropCard, MatchView, PostView, RoleView } from "@circuit/ui";
import { roleLabel } from "@/lib/format";
import { api, unwrap } from "./client";
import { useKey } from "./keys";
import { toUpdate, type LiveWireItem } from "./livewire";
import { toPerson, toPost, toRole } from "./mappers";
import { useFeatures } from "./features";
import { useMe } from "./me";
import { PARTNER_STAND_IN, PROMOTED_STAND_IN } from "./missing";
import { MOCK } from "./mocks/config";

export type { LiveWireItem };

/** Live wire: up to 12 updates from the last 24 hours, ready for the UI package. */
export function useLiveWire() {
  const { key, enabled } = useKey("livewire");
  return useQuery({ queryKey: key, enabled, queryFn: async () => (await unwrap(api.GET("/api/livewire"))).map(toUpdate) });
}

/** Marks an update as opened; the node dims straight away without waiting for a refetch. */
export function useMarkUpdateSeen() {
  const qc = useQueryClient();
  const { key } = useKey("livewire");
  return useMutation({
    mutationFn: (updateKey: string) => unwrap(api.POST("/api/livewire/seen", { body: { key: updateKey } })),
    onMutate: (updateKey) => {
      qc.setQueryData<LiveWireItem[]>(key, (old) => old?.map((x) => (x.key === updateKey ? { ...x, seen: true } : x)));
    },
  });
}

export type DailyDrop = { cards: DropCard[]; nextDropAt: string };

/** What Home draws. A feature that is off is simply absent (DESIGN.md §3); under-18 members get no Daily Drop (the backend builds none for them). */
export function useHome() {
  const features = useFeatures();
  const me = useMe().data;
  const pulse = features.on("pulse");
  const minor = me?.isMinor ?? false;
  const drop = features.on("daily_drop") && !minor;
  return { ready: features.ready && !!me, pulse, drop, minor, empty: !pulse && !drop };
}

/** Today's three people, each with the reason first (DESIGN.md §4 Home). */
export function useDailyDrop() {
  const { key, enabled } = useKey("drop");
  return useQuery({
    queryKey: key,
    enabled,
    queryFn: async (): Promise<DailyDrop> => {
      const d = await unwrap(api.GET("/api/drop/today"));
      const cards: DropCard[] = d.cards.map((c) => {
        const [lead, ...rest] = c.reason.split(/(?<=\.)\s+/);
        return {
          id: c.member.id,
          person: toPerson(c.member),
          reason: lead,
          detail: rest.join(" "),
          helpWith: c.help_with,
          offers: c.offers_you_need,
          strength: c.strength,
          via: c.via ? { id: c.via.id, name: c.via.display_name, role: roleLabel(c.via.role) } : null,
          image: c.image ? { src: c.image.w1440, alt: c.image.alt } : null,
          bridge: c.is_bridge,
          answered: (c.outcome as "intro" | "skip" | null) ?? null,
        };
      });
      return { cards, nextDropAt: d.next_drop_at };
    },
  });
}

/** Records a skip. (An intro goes through `useRequestIntro`, which records its own swipe once the intro is sent.) */
export function useSkip() {
  const qc = useQueryClient();
  const { key } = useKey("drop");
  return useMutation({
    mutationFn: (id: number) => unwrap(api.POST("/api/drop/today/{member_id}/swipe", { params: { path: { member_id: id } }, body: { direction: "skip" } })),
    onError: () => qc.invalidateQueries({ queryKey: key }),
  });
}

export type PulseEntry =
  | { kind: "post"; key: string; post: PostView }
  | { kind: "role"; key: string; role: RoleView }
  | { kind: "activity"; key: string; type: "circuit_completed" | "intro_accepted" | "startup_claimed"; text: string }
  | { kind: "skills"; key: string; skills: Array<{ name: string; roles: number }> }
  | { kind: "partner"; key: string; org: string; text: string }
  | { kind: "promoted"; key: string; startup: string; role: RoleView; why: string };

function activityText(a: { type: string; startup_name?: string | null }): { type: "circuit_completed" | "intro_accepted" | "startup_claimed"; text: string } {
  if (a.type === "circuit_completed") return { type: "circuit_completed", text: "A circuit closed in your network. Three people helped each other." };
  if (a.type === "intro_accepted") return { type: "intro_accepted", text: "Your intro was accepted." };
  return { type: "startup_claimed", text: `${a.startup_name ?? "A startup"} claimed its profile near you.` };
}

/** Pulse: chronological, last 7 days. `includeSeen` brings back what was already shown ("See earlier this week"). */
export function usePulse(includeSeen: boolean) {
  const { key, enabled } = useKey("pulse", includeSeen);
  const meId = useMe().data?.id;
  const features = useFeatures();
  const [hidden, setHidden] = useState<string[]>([]);
  const q = useInfiniteQuery({
    queryKey: key,
    enabled,
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) => unwrap(api.GET("/api/pulse", { params: { query: { cursor: pageParam, limit: 20, include_seen: includeSeen } } })),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
  const items: PulseEntry[] = (q.data?.pages.flatMap((p) => p.items) ?? []).flatMap((it): PulseEntry[] => {
    if (it.kind === "post" && it.post) return [{ kind: "post", key: it.key, post: toPost(it.post, meId) }];
    if (it.kind === "role" && it.role) return [{ kind: "role", key: it.key, role: toRole(it.role) }];
    if (it.kind === "activity" && it.activity) return [{ kind: "activity", key: it.key, ...activityText(it.activity) }];
    if (it.kind === "skills_in_demand" && it.skills_in_demand) {
      return [{ kind: "skills", key: it.key, skills: it.skills_in_demand.skills.map((s) => ({ name: s.name, roles: s.open_roles })) }];
    }
    return [];
  });
  // Partner and promoted slots exist only when their flag is on, never first, at most one promoted per 8 items and one partner per 10
  // (DESIGN.md §4). The API sends neither yet, so mock mode shows stand-ins; a real build draws none.
  if (MOCK && items.length >= 2 && features.raw("promotions") && !hidden.includes(PROMOTED_STAND_IN.key)) {
    items.splice(2, 0, { kind: "promoted", key: PROMOTED_STAND_IN.key, startup: PROMOTED_STAND_IN.startup, role: PROMOTED_STAND_IN.role, why: PROMOTED_STAND_IN.why });
  }
  if (MOCK && items.length >= 4 && features.raw("partner_mode")) {
    items.splice(4, 0, { kind: "partner", key: PARTNER_STAND_IN.key, org: PARTNER_STAND_IN.org, text: PARTNER_STAND_IN.text });
  }
  const lastPage = q.data?.pages[q.data.pages.length - 1];
  return {
    hidePromotion: (key: string) => setHidden((h) => [...h, key]),
    items,
    caughtUp: !!lastPage && !q.hasNextPage && lastPage.caught_up,
    isPending: q.isPending,
    isError: q.isError,
    hasNextPage: q.hasNextPage,
    isFetchingNextPage: q.isFetchingNextPage,
    fetchNextPage: q.fetchNextPage,
  };
}

export function useMarkPulseSeen() {
  return useMutation({ mutationFn: () => unwrap(api.POST("/api/pulse/seen")) });
}

export function useReact() {
  return useMutation({
    mutationFn: ({ post, kind, on }: { post: number; kind: "helpful" | "intro_me" | "lets_talk"; on: boolean }) =>
      on
        ? unwrap(api.PUT("/api/posts/{post_id}/reactions/{kind}", { params: { path: { post_id: post, kind } } }))
        : unwrap(api.DELETE("/api/posts/{post_id}/reactions/{kind}", { params: { path: { post_id: post, kind } } })),
  });
}

export type ReportTarget = "post" | "reply" | "message" | "member" | "startup";
export function useReport() {
  return useMutation({
    mutationFn: (r: { target_type: ReportTarget; target_id: number; reason: string }) => unwrap(api.POST("/api/reports", { body: r })),
  });
}

/** People worth meeting, each with a one-line reason. `offset` lets the desktop rail continue after the Daily Drop's three. */
export function useMatches(opts: { limit?: number; offset?: number } = {}) {
  const { limit = 5, offset = 0 } = opts;
  const { key, enabled } = useKey("matches", limit, offset);
  return useQuery({
    queryKey: key,
    enabled,
    queryFn: async () => {
      const page = await unwrap(api.GET("/api/matches", { params: { query: { limit, offset } } }));
      const items: MatchView[] = page.items.map((m) => ({
        id: m.candidate_id,
        person: { id: m.candidate_id, name: m.display_name, role: roleLabel(m.role), headline: "", place: m.city, level: m.verification_level },
        strength: m.strength,
        reason: m.reason,
        bridge: m.is_bridge,
      }));
      return { items };
    },
  });
}
