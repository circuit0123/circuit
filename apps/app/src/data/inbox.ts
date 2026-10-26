"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { roleLabel } from "@/lib/format";
import { api, ApiError, unwrap } from "./client";
import { useKey } from "./keys";
import { useMe } from "./me";
import { useChannels } from "./realtime";

type Conv = Schemas["ConversationOut"];
export type Folder = "chats" | "requests";

export type InboxRow = {
  id: number;
  other: { id: number; name: string };
  /** The last message in one line: "You: Sent the repo link." or "Photo". */
  preview: string;
  /** "9:41 am", "Yesterday", "Tue", "12 Oct" (IST). */
  time: string;
  unread: boolean;
  /** A request the viewer started and is waiting on. */
  waiting: boolean;
};

const IST = "Asia/Kolkata";
const dayKey = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: IST }).format(d);

/** When a conversation last moved, the way messaging apps say it. */
export function inboxTime(iso: string | null, now = new Date()): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (dayKey(d) === dayKey(now)) return new Intl.DateTimeFormat("en-IN", { timeZone: IST, hour: "numeric", minute: "2-digit", hour12: true }).format(d).replace(/\s?([ap])m/i, (_, x: string) => ` ${x.toLowerCase()}m`);
  if (dayKey(d) === dayKey(new Date(now.getTime() - 86_400_000))) return "Yesterday";
  if (now.getTime() - d.getTime() < 6 * 86_400_000) return new Intl.DateTimeFormat("en-IN", { timeZone: IST, weekday: "short" }).format(d);
  return new Intl.DateTimeFormat("en-IN", { timeZone: IST, day: "numeric", month: "short" }).format(d);
}

export function previewOf(m: Conv["last_message"]): string {
  if (!m) return "";
  if (m.removed) return "Message removed";
  const text = m.body.trim() || (m.image ? "Photo" : "");
  return m.mine ? `You: ${text}` : text;
}

export const toInboxRow = (c: Conv): InboxRow => ({
  id: c.id,
  other: { id: c.other.id, name: c.other.display_name },
  preview: previewOf(c.last_message),
  time: inboxTime(c.last_message_at),
  unread: c.unread > 0,
  waiting: c.status === "request" && c.started_by_me,
});

export const inboxKey = (folder: Folder) => ["inbox", folder];

/**
 * One Inbox folder (DESIGN.md §4 Inbox): `chats` (connections and accepted requests) or `requests` (first messages from people the
 * viewer isn't connected to). Members under 18 have no Requests folder at all. Listens to every listed conversation's Realtime channel
 * (`conversation:<id>`, event `message`) and refreshes on a new message; new conversations arrive with the minute poll (there is no
 * per-member conversation channel yet: PROGRESS.md "Frontend → API needed").
 */
export function useInbox(folder: Folder) {
  const me = useMe().data;
  const { enabled } = useKey();
  const qc = useQueryClient();
  const allowed = folder === "chats" || (!!me && !me.isMinor);
  const q = useQuery({
    queryKey: inboxKey(folder),
    enabled: enabled && allowed,
    refetchInterval: 60_000,
    queryFn: () => unwrap(api.GET("/api/conversations", { params: { query: { folder } } })),
  });
  const rows = (q.data ?? []).map(toInboxRow);
  useChannels(rows.map((r) => `conversation:${r.id}`), "message", () => qc.invalidateQueries({ queryKey: ["inbox"] }));
  return { rows, allowed, isPending: allowed && q.isPending, isError: q.isError, refetch: q.refetch };
}

/** Whether the Inbox tab gets its dot: anything unread in Chats, or in Requests for members who have them. */
export function useInboxDot(): boolean {
  const chats = useInbox("chats");
  const requests = useInbox("requests");
  return chats.rows.some((r) => r.unread) || (requests.allowed && requests.rows.some((r) => r.unread));
}

export type Connection = { id: number; name: string; line: string };

/** People the viewer is connected to: who "New message" can write to. */
export function useConnections(enabledNow = true) {
  const { key, enabled } = useKey("connections");
  return useQuery({
    queryKey: key,
    enabled: enabled && enabledNow,
    queryFn: async (): Promise<Connection[]> =>
      (await unwrap(api.GET("/api/connections"))).map((a) => ({ id: a.id, name: a.display_name, line: [roleLabel(a.role), a.city].filter(Boolean).join(" · ") })),
  });
}

/** The conversation already open with someone, if any (so "New message" to an existing chat opens it). */
export function useFindConversation() {
  const qc = useQueryClient();
  return (memberId: number): number | null => {
    for (const f of ["chats", "requests"] as const) {
      const hit = qc.getQueryData<Conv[]>(inboxKey(f))?.find((c) => c.other.id === memberId);
      if (hit) return hit.id;
    }
    return null;
  };
}

/** Sends the first message to someone. Connections chat at once; anyone else gets it as a request. */
export function useStartConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (b: { member_id: number; body: string; upload_id?: number | null }) => unwrap(api.POST("/api/conversations", { body: b })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inbox"] }),
  });
}

export type ConnectionRequestRow = { id: number; from: { id: number; name: string; line: string }; note: string };

/** People who asked to connect with the viewer and are waiting for an answer (newest first). */
export function useConnectionRequests() {
  const { enabled } = useKey();
  const q = useQuery({
    queryKey: ["connection-requests"],
    enabled,
    refetchInterval: 60_000,
    queryFn: async (): Promise<ConnectionRequestRow[]> =>
      (await unwrap(api.GET("/api/connections/requests", { params: { query: { box: "incoming" } } }))).map((r) => ({
        id: r.id,
        from: { id: r.sender.id, name: r.sender.display_name, line: [r.sender.headline || roleLabel(r.sender.role), r.sender.city].filter(Boolean).join(" · ") },
        note: r.note,
      })),
  });
  return { rows: q.data ?? [], isPending: q.isPending, isError: q.isError, refetch: q.refetch };
}

/** Accept or decline a connection request. Already answered (409) counts as done, so the row just goes away. */
export function useRespondConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, accept }: { id: number; accept: boolean }) => {
      try { await unwrap(api.POST("/api/connections/requests/{request_id}/respond", { params: { path: { request_id: id } }, body: { accept } })); }
      catch (e) { if (!(e instanceof ApiError && e.code === "already_answered")) throw e; }
    },
    onMutate: ({ id }) => { qc.setQueryData<ConnectionRequestRow[]>(["connection-requests"], (old) => old?.filter((r) => r.id !== id)); },
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["connection-requests"] });
      qc.invalidateQueries({ queryKey: ["connections"] });
      qc.invalidateQueries({ queryKey: ["unread"] });
    },
  });
}
