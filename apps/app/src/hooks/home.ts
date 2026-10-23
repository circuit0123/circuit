"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { api, unwrap } from "@/lib/api";
import { useSession } from "@/components/Providers";
import { toUpdate, type LiveWireItem } from "@/lib/livewire";

/** Every query is keyed by the token so switching persona never shows someone else's data. */
function useKey(...k: unknown[]) {
  const { token } = useSession();
  return { key: [token, ...k], enabled: !!token };
}

export function useMe() {
  const { key, enabled } = useKey("me");
  return useQuery({ queryKey: key, enabled, queryFn: () => unwrap(api.GET("/api/me")) });
}

export function useLiveWire() {
  const { key, enabled } = useKey("livewire");
  return useQuery({ queryKey: key, enabled, queryFn: async () => (await unwrap(api.GET("/api/livewire"))).map(toUpdate) });
}

/** Marks an update as opened; the node dims straight away without waiting for a refetch. */
export function useMarkUpdateSeen() {
  const qc = useQueryClient();
  const { token } = useSession();
  return useMutation({
    mutationFn: (key: string) => unwrap(api.POST("/api/livewire/seen", { body: { key } })),
    onMutate: (key) => {
      qc.setQueryData<LiveWireItem[]>([token, "livewire"], (old) => old?.map((x) => (x.key === key ? { ...x, seen: true } : x)));
    },
  });
}

export function useDrop() {
  const { key, enabled } = useKey("drop");
  return useQuery({ queryKey: key, enabled, queryFn: () => unwrap(api.GET("/api/drop/today")) });
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
