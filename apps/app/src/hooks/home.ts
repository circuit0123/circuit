"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { api, unwrap } from "@/lib/api";
import { useSession } from "@/components/Providers";
import { fromToday } from "@/lib/livewire";
import { strengthLabel } from "@circuit/ui";

/** Every query is keyed by the token so switching persona never shows someone else's data. */
function useKey(...k: unknown[]) {
  const { token } = useSession();
  return { key: [token, ...k], enabled: !!token };
}

export function useMe() {
  const { key, enabled } = useKey("me");
  return useQuery({ queryKey: key, enabled, queryFn: () => unwrap(api.GET("/api/me")) });
}

export function useToday() {
  const { key, enabled } = useKey("today");
  return useQuery({ queryKey: key, enabled, queryFn: () => unwrap(api.GET("/api/today")) });
}

/** The Live wire. TODO(livewire-endpoint): read GET /api/livewire directly once the backend has it. */
export function useLiveWire() {
  const { key, enabled } = useKey("today");
  return useQuery({ queryKey: key, enabled, queryFn: async () => fromToday(await unwrap(api.GET("/api/today"))) });
}

export function useMarkCircleSeen() {
  const qc = useQueryClient();
  const { token } = useSession();
  return useMutation({
    mutationFn: (c: { id: number; kind: "member" | "startup" }) => unwrap(api.POST("/api/today/seen", { body: c })),
    onSuccess: (_d, c) => {
      qc.setQueryData<Schemas["CircleOut"][]>([token, "today"], (old) => old?.map((x) => (x.id === c.id && x.kind === c.kind ? { ...x, seen: true } : x)));
    },
  });
}

/**
 * Today's drop with a match strength per card. TODO(drop-strength): the backend will return `strength`, `help_with`
 * and `offers_you_need` on each card; then drop the /api/matches join and the reason parsing below.
 */
export function useDrop() {
  const { key, enabled } = useKey("drop");
  return useQuery({
    queryKey: key,
    enabled,
    queryFn: async () => {
      const [drop, matches] = await Promise.all([
        unwrap(api.GET("/api/drop/today")),
        unwrap(api.GET("/api/matches", { params: { query: { limit: 100, offset: 0 } } })).catch(() => null),
      ]);
      const score = new Map(matches?.items.map((m) => [m.candidate_id, m.score_percent / 100]));
      return {
        ...drop,
        cards: drop.cards.map((c) => {
          const help = /^They offer (.+?), which you need/.exec(c.reason)?.[1] ?? null;
          const sc = score.get(c.member.id);
          // "They offer X, which you need." is now the card headline; keep only what the sentence adds.
          const rest = help ? c.reason.replace(/^They offer .+?, which you need\.?\s*/, "") : c.reason;
          return { ...c, reason: rest, strength: sc === undefined ? null : strengthLabel(sc), helpWith: help, offers: help ? [help] : [] };
        }),
      };
    },
  });
}

/** Records the swipe; an "intro" swipe also asks for the intro (the backend routes it via a mutual if one exists). */
export function useSwipe() {
  return useMutation({
    mutationFn: async ({ id, direction }: { id: number; direction: "intro" | "skip" }) => {
      await unwrap(api.POST("/api/drop/today/{member_id}/swipe", { params: { path: { member_id: id } }, body: { direction } }));
      if (direction === "intro") await unwrap(api.POST("/api/intros", { body: { target_id: id, message: "" } }));
    },
  });
}

export function usePulse(includeSeen: boolean) {
  const { key, enabled } = useKey("pulse", includeSeen);
  return useInfiniteQuery({
    queryKey: key,
    enabled,
    initialPageParam: undefined as string | undefined,
    queryFn: ({ pageParam }) =>
      unwrap(api.GET("/api/pulse", { params: { query: { cursor: pageParam, limit: 20, include_seen: includeSeen } } })),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });
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

export function useReport() {
  return useMutation({
    mutationFn: (r: { target_type: "post" | "member"; target_id: number; reason: string }) => unwrap(api.POST("/api/reports", { body: r })),
  });
}

export function useUnreadCount() {
  const { key, enabled } = useKey("unread");
  return useQuery({ queryKey: key, enabled, queryFn: () => unwrap(api.GET("/api/notifications/unread-count")), refetchInterval: 60_000 });
}

/** People after the three in today's drop, for the desktop right rail. */
export function useMorePeople() {
  const { key, enabled } = useKey("people-more");
  return useQuery({ queryKey: key, enabled, queryFn: () => unwrap(api.GET("/api/matches", { params: { query: { limit: 4, offset: 3 } } })) });
}

/** Asks for an intro (the backend routes it via a mutual if one exists). */
export function useRequestIntro() {
  return useMutation({ mutationFn: (id: number) => unwrap(api.POST("/api/intros", { body: { target_id: id, message: "" } })) });
}
