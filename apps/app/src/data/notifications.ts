"use client";

import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { useKey } from "./keys";

/**
 * The bell's dot. The API answers `{count}`, but two backend schemas share the name `CountOut` and the OpenAPI file keeps the
 * dashboard's `{hidden, value}` one (listed in PROGRESS.md "Frontend → API needed"), so the real shape is read here.
 * Polled once a minute; Realtime `member:<id>` nudges come with the notification centre.
 */
export function useUnreadCount() {
  const { key, enabled } = useKey("unread");
  return useQuery({ queryKey: key, enabled, refetchInterval: 60_000, queryFn: async () => Number(((await unwrap(api.GET("/api/notifications/unread-count"))) as unknown as { count?: number }).count ?? 0) });
}
