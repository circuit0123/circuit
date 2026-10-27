"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useEffect } from "react";
import type { Schemas } from "@circuit/api-client";
import { api, unwrap } from "./client";
import { useKey } from "./keys";
import { notificationHref } from "./links";
import { useMe } from "./me";
import { MOCK } from "./mocks/config";
import { getSupabase } from "./supabase";

type Page = Schemas["Page_NotificationOut_"];

export type NotificationRow = {
  id: number;
  text: string;
  /** Who did it, when a person did; system notices have none. */
  actor: { id: number; name: string } | null;
  /** "9:41 am", IST. */
  time: string;
  unread: boolean;
  /** Where a tap goes (data/links.ts). */
  href: string;
};
export type NotificationGroup = { day: string; items: NotificationRow[] };

const IST = "Asia/Kolkata";
const dayKey = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: IST }).format(d); // YYYY-MM-DD
const timeOf = (d: Date) => new Intl.DateTimeFormat("en-IN", { timeZone: IST, hour: "numeric", minute: "2-digit", hour12: true }).format(d).replace(/\s?([ap])m/i, (_, x: string) => ` ${x.toLowerCase()}m`);

/** "Today", "Yesterday", the weekday for the rest of the week, then "12 October". Days are IST days. */
export function dayLabel(d: Date, now = new Date()): string {
  const key = dayKey(d);
  if (key === dayKey(now)) return "Today";
  if (key === dayKey(new Date(now.getTime() - 86_400_000))) return "Yesterday";
  const age = (now.getTime() - d.getTime()) / 86_400_000;
  if (age < 7) return new Intl.DateTimeFormat("en-IN", { timeZone: IST, weekday: "long" }).format(d);
  const sameYear = new Intl.DateTimeFormat("en-IN", { timeZone: IST, year: "numeric" }).format(d) === new Intl.DateTimeFormat("en-IN", { timeZone: IST, year: "numeric" }).format(now);
  return new Intl.DateTimeFormat("en-IN", { timeZone: IST, day: "numeric", month: "long", ...(sameYear ? {} : { year: "numeric" }) }).format(d);
}

/** Newest first, as the API sends them, grouped by day. */
export function groupByDay(items: Schemas["NotificationOut"][], now = new Date()): NotificationGroup[] {
  const groups: NotificationGroup[] = [];
  for (const n of items) {
    const at = new Date(n.created_at);
    const day = dayLabel(at, now);
    const row: NotificationRow = {
      id: n.id,
      text: n.text,
      actor: n.actor ? { id: n.actor.id, name: n.actor.display_name } : null,
      time: timeOf(at),
      unread: !n.read,
      href: notificationHref(n.target),
    };
    const last = groups[groups.length - 1];
    if (last?.day === day) last.items.push(row);
    else groups.push({ day, items: [row] });
  }
  return groups;
}

/**
 * The bell's dot. The API answers `{count}`, but two backend schemas share the name `CountOut` and the OpenAPI file keeps the
 * dashboard's `{hidden, value}` one (listed in PROGRESS.md "Frontend → API needed"), so the real shape is read here.
 * Polled once a minute; Realtime nudges (`useNotificationNudges`) bring a new one at once.
 */
export function useUnreadCount() {
  const { key, enabled } = useKey("unread");
  return useQuery({ queryKey: key, enabled, refetchInterval: 60_000, queryFn: async () => Number(((await unwrap(api.GET("/api/notifications/unread-count"))) as unknown as { count?: number }).count ?? 0) });
}

/** The notification centre, newest first and grouped by day. Twenty at a time; `loadMore` fetches the next twenty. */
export function useNotifications() {
  const { key, enabled } = useKey("notifications");
  const q = useInfiniteQuery({
    queryKey: key,
    enabled,
    initialPageParam: 0,
    queryFn: ({ pageParam }) => unwrap(api.GET("/api/notifications", { params: { query: { limit: 20, offset: pageParam } } })),
    getNextPageParam: (last) => last.next_offset ?? undefined,
  });
  return {
    groups: groupByDay(q.data?.pages.flatMap((p) => p.items) ?? []),
    isPending: q.isPending,
    isError: q.isError,
    hasMore: q.hasNextPage,
    loadMore: () => q.fetchNextPage(),
    isLoadingMore: q.isFetchingNextPage,
    refetch: q.refetch,
  };
}

/** Marks one read. The dot goes and the bell's count drops at once; a failure brings them back. */
export function useMarkRead() {
  const qc = useQueryClient();
  const { key } = useKey("notifications");
  const unread = useKey("unread").key;
  return useMutation({
    mutationFn: (id: number) => unwrap(api.POST("/api/notifications/{notification_id}/read", { params: { path: { notification_id: id } } })),
    onMutate: (id) => {
      let wasUnread = false;
      qc.setQueryData<InfiniteData<Page>>(key, (old) => old && {
        ...old,
        pages: old.pages.map((p) => ({ ...p, items: p.items.map((n) => { if (n.id === id && !n.read) { wasUnread = true; return { ...n, read: true }; } return n; }) })),
      });
      if (wasUnread) qc.setQueryData<number>(unread, (c) => Math.max(0, (c ?? 0) - 1));
    },
    onError: () => { qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: unread }); },
  });
}

/** Marks everything read: the dots go and the bell clears at once; a failure brings them back. */
export function useMarkAllRead() {
  const qc = useQueryClient();
  const { key } = useKey("notifications");
  const unread = useKey("unread").key;
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/notifications/read-all")),
    onMutate: () => {
      qc.setQueryData<InfiniteData<Page>>(key, (old) => old && { ...old, pages: old.pages.map((p) => ({ ...p, items: p.items.map((n) => ({ ...n, read: true })) })) });
      qc.setQueryData<number>(unread, 0);
    },
    onError: () => { qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: unread }); },
  });
}

/**
 * Listens on the member's own Realtime channel (`member:<id>`, event `notification`, id only) and refreshes the bell and the list when one
 * arrives. Used once, by the shell. Does nothing without a Supabase session (dev personas, mock mode); the minute poll covers those.
 */
export function useNotificationNudges() {
  const qc = useQueryClient();
  const meId = useMe().data?.id;
  const { token } = useKey();
  useEffect(() => {
    const sb = getSupabase();
    if (MOCK || !sb || !meId || !token) return;
    let channel: ReturnType<typeof sb.channel> | null = null;
    let cancelled = false;
    sb.auth.getSession().then(({ data }) => {
      if (cancelled || !data.session) return;
      channel = sb
        .channel(`member:${meId}`, { config: { private: true } })
        .on("broadcast", { event: "notification" }, () => {
          qc.invalidateQueries({ queryKey: ["unread"] });
          qc.invalidateQueries({ queryKey: ["notifications"] });
        })
        .subscribe();
    });
    return () => { cancelled = true; if (channel) sb.removeChannel(channel); };
  }, [meId, token, qc]);
}
