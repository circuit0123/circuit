"use client";

import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Schemas } from "@circuit/api-client";
import { roleLabel } from "@/lib/format";
import { api, unwrap } from "./client";
import { useReport } from "./home";
import { inboxKey, type Folder } from "./inbox";
import { useKey } from "./keys";
import { dayLabel } from "./notifications";
import { MOCK } from "./mocks/config";
import { useChannel } from "./realtime";

type Msg = Schemas["MessageOut"];
type Conv = Schemas["ConversationOut"];
type MsgPage = Schemas["MessagePage"];

export type Bubble = {
  key: string;
  mine: boolean;
  body: string;
  image: { src: string; width: number; height: number; alt: string } | null;
  removed: boolean;
  /** Only the viewer's own messages that haven't reached the server yet are `sending` or `failed`. */
  state: "sent" | "sending" | "failed";
  /** For a failed message: send it again. */
  tempId?: string;
};
export type BubbleDay = { day: string; items: Bubble[] };

export type ConversationHead = {
  id: number;
  other: { id: number; name: string; line: string };
  /** `received`: a request to the viewer, waiting for Accept. `sent`: the viewer's own request, waiting for the other person. */
  request: "received" | "sent" | null;
};

/** Types and size the API takes for message images (UploadIn), checked before anything is sent. */
export const IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;
export const MAX_IMAGE_BYTES = 5 * 1024 * 1024;
export type ImageProblem = "type" | "size";
export function imageProblem(f: File): ImageProblem | null {
  if (!(IMAGE_TYPES as readonly string[]).includes(f.type)) return "type";
  if (f.size > MAX_IMAGE_BYTES) return "size";
  return null;
}

/** Uploads one image for a message: ask for a signed URL, PUT the file there, then confirm. Returns the upload id to send with. */
async function uploadImage(file: File): Promise<number> {
  const up = await unwrap(api.POST("/api/media/uploads", { body: { purpose: "message", content_type: file.type as (typeof IMAGE_TYPES)[number], size: file.size } }));
  const put = await fetch(up.upload_url, { method: "PUT", body: file, headers: { "content-type": file.type } });
  if (!put.ok) throw new Error("upload failed");
  await unwrap(api.POST("/api/media/uploads/{upload_id}/complete", { params: { path: { upload_id: up.id } } }));
  return up.id;
}

type Pending = { tempId: string; body: string; file: File | null; preview: string | null; at: string; state: "sending" | "failed"; image: { width: number; height: number } | null };

const imageOf = (m: Msg, who: string): Bubble["image"] => {
  const i = m.image as { width?: number; height?: number; w480?: string; w1440?: string } | null;
  if (!i || !(i.w480 || i.w1440)) return null;
  return { src: (i.w480 ?? i.w1440)!, width: i.width ?? 4, height: i.height ?? 3, alt: m.mine ? "Photo you sent" : `Photo from ${who}` };
};

/** Oldest first, grouped by IST day ("Today", "Yesterday", …), with the viewer's unsent messages at the end. */
export function groupBubbles(messages: Msg[], pending: Pending[], otherName: string, now = new Date()): BubbleDay[] {
  const out: BubbleDay[] = [];
  const push = (at: string, b: Bubble) => {
    const day = dayLabel(new Date(at), now);
    const last = out[out.length - 1];
    if (last?.day === day) last.items.push(b);
    else out.push({ day, items: [b] });
  };
  for (const m of messages) push(m.created_at, { key: `m${m.id}`, mine: m.mine, body: m.removed ? "" : m.body, image: m.removed ? null : imageOf(m, otherName), removed: m.removed, state: "sent" });
  for (const p of pending) {
    push(p.at, {
      key: p.tempId, mine: true, body: p.body, removed: false, state: p.state, tempId: p.tempId,
      image: p.preview ? { src: p.preview, width: p.image?.width ?? 4, height: p.image?.height ?? 3, alt: "Photo you're sending" } : null,
    });
  }
  return out;
}

const naturalSize = (src: string) => new Promise<{ width: number; height: number } | null>((resolve) => {
  const img = new Image();
  img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
  img.onerror = () => resolve(null);
  img.src = src;
});

/** Adds a message to the newest page of the cache once (by id). */
function addMessage(old: InfiniteData<MsgPage> | undefined, m: Msg): InfiniteData<MsgPage> | undefined {
  if (!old) return old;
  if (old.pages.some((p) => p.items.some((x) => x.id === m.id))) return old;
  const [first, ...rest] = old.pages;
  return { ...old, pages: [{ ...first, items: [m, ...first.items] }, ...rest] };
}

/** Zeroes a conversation's unread count in both Inbox folders. */
function clearUnread(qc: ReturnType<typeof useQueryClient>, id: number) {
  for (const f of ["chats", "requests"] as Folder[]) qc.setQueryData<Conv[]>(inboxKey(f), (old) => old?.map((c) => (c.id === id ? { ...c, unread: 0 } : c)));
}

/**
 * One conversation (DESIGN.md §4 Inbox, Chat.dc.html). Owns everything the screen needs:
 * - the other person and whether this is a request (received: Accept first; sent: waiting),
 * - messages oldest first by day, with `loadOlder` for history,
 * - `send(text, file?)`: optimistic; the bubble shows at once as "sending", turns "failed" if the call fails, and `retry` sends it again,
 * - Realtime: listens on `conversation:<id>` (event `message`, ids only), fetches the new message and marks it read,
 * - marks the conversation read when it opens (read receipts are never shown to senders: off by default, DESIGN.md §4).
 */
export function useConversation(id: number) {
  const qc = useQueryClient();
  const { enabled } = useKey();
  const valid = Number.isFinite(id) && id > 0;
  const convKey = ["conversation", id];
  const msgKey = ["messages", id];

  const conv = useQuery({
    queryKey: convKey,
    enabled: enabled && valid,
    queryFn: () => unwrap(api.GET("/api/conversations/{conversation_id}", { params: { path: { conversation_id: id } } })),
  });
  const msgs = useInfiniteQuery({
    queryKey: msgKey,
    enabled: enabled && valid,
    initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => unwrap(api.GET("/api/conversations/{conversation_id}/messages", { params: { path: { conversation_id: id }, query: { limit: 30, cursor: pageParam } } })),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  // Mark read: when it opens with something unread, and after each message that arrives while it's open.
  const markRead = useCallback(() => {
    clearUnread(qc, id);
    api.POST("/api/conversations/{conversation_id}/read", { params: { path: { conversation_id: id } } }).catch(() => { /* next open tries again */ });
  }, [qc, id]);
  const c = conv.data;
  useEffect(() => { if (c && c.unread > 0) markRead(); }, [c, markRead]);

  useChannel(valid ? `conversation:${id}` : null, "message", async (p) => {
    const mid = Number(p.message_id);
    if (!mid) return;
    try {
      const m = await unwrap(api.GET("/api/conversations/{conversation_id}/messages/{message_id}", { params: { path: { conversation_id: id, message_id: mid } } }));
      qc.setQueryData<InfiniteData<MsgPage>>(msgKey, (old) => addMessage(old, m));
      if (!m.mine) markRead();
      qc.invalidateQueries({ queryKey: convKey });
    } catch {
      qc.invalidateQueries({ queryKey: msgKey });
    }
  });

  // Optimistic sending.
  const [pending, setPending] = useState<Pending[]>([]);
  const seq = useRef(0);
  const deliver = useCallback(async (p: Pending) => {
    setPending((list) => list.map((x) => (x.tempId === p.tempId ? { ...x, state: "sending" } : x)));
    try {
      const upload_id = p.file ? await uploadImage(p.file) : null;
      const m = await unwrap(api.POST("/api/conversations/{conversation_id}/messages", { params: { path: { conversation_id: id } }, body: { body: p.body, upload_id } }));
      qc.setQueryData<InfiniteData<MsgPage>>(msgKey, (old) => addMessage(old, m));
      setPending((list) => list.filter((x) => x.tempId !== p.tempId));
      qc.invalidateQueries({ queryKey: convKey });
      qc.invalidateQueries({ queryKey: ["inbox"] });
    } catch {
      setPending((list) => list.map((x) => (x.tempId === p.tempId ? { ...x, state: "failed" } : x)));
    }
    // msgKey/convKey are rebuilt each render from `id`; `id` is the real dependency.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, qc]);

  const send = useCallback(async (text: string, file: File | null = null) => {
    const body = text.trim();
    if (!body && !file) return;
    const preview = file ? URL.createObjectURL(file) : null;
    const image = preview ? await naturalSize(preview) : null;
    const p: Pending = { tempId: `t${++seq.current}`, body, file, preview, at: new Date().toISOString(), state: "sending", image };
    setPending((list) => [...list, p]);
    void deliver(p);
  }, [deliver]);
  const retry = useCallback((tempId: string) => {
    const p = pending.find((x) => x.tempId === tempId);
    if (p) void deliver(p);
  }, [pending, deliver]);

  const accept = useMutation({
    mutationFn: () => unwrap(api.POST("/api/conversations/{conversation_id}/accept", { params: { path: { conversation_id: id } } })),
    onSuccess: (next) => { qc.setQueryData(convKey, next); qc.invalidateQueries({ queryKey: ["inbox"] }); },
  });
  const block = useMutation({
    mutationFn: () => unwrap(api.POST("/api/conversations/{conversation_id}/block", { params: { path: { conversation_id: id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inbox"] }),
  });
  const report = useReport();
  /** Say no to a request without blocking: it disappears for me, the sender is not told. */
  const decline = useMutation({
    mutationFn: () => unwrap(api.POST("/api/conversations/{conversation_id}/decline", { params: { path: { conversation_id: id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["inbox"] }),
  });

  const head: ConversationHead | undefined = c && {
    id: c.id,
    other: { id: c.other.id, name: c.other.display_name, line: [roleLabel(c.other.role), c.other.city].filter(Boolean).join(" · ") },
    request: c.status === "request" ? (c.started_by_me ? "sent" : "received") : null,
  };
  const all = (msgs.data?.pages ?? []).flatMap((pg) => pg.items).slice().reverse();
  const days = groupBubbles(all, pending, head?.other.name ?? "");
  const sentWhileWaiting = head?.request === "sent" && (all.some((m) => m.mine) || pending.length > 0);

  return {
    head,
    days,
    /** The newest bubble's key: the screen scrolls to it when it changes. */
    lastKey: days.at(-1)?.items.at(-1)?.key ?? null,
    isPending: conv.isPending || msgs.isPending,
    isError: conv.isError || msgs.isError,
    notFound: conv.isError && (conv.error as { status?: number })?.status === 404,
    refetch: () => { conv.refetch(); msgs.refetch(); },
    hasOlder: msgs.hasNextPage,
    loadOlder: () => msgs.fetchNextPage(),
    isLoadingOlder: msgs.isFetchingNextPage,
    send,
    retry,
    /** In a request the sender gets one message until the other person answers. */
    canSend: !!head && head.request !== "received" && !sentWhileWaiting,
    accept,
    block,
    report: (reason: string) => report.mutateAsync({ target_type: "member", target_id: head?.other.id ?? 0, reason }),
    canDecline: head?.request === "received",
    decline,
  };
}

export type DraftPerson = { id: number; name: string; line: string };

/**
 * A conversation that doesn't exist yet ("New message" to a connection, or "Reply" on a Live wire update). The first send starts it (`POST /api/conversations`);
 * `onStarted` gets the new id so the screen can move to it.
 */
export function useDraftConversation(memberId: number, onStarted: (conversationId: number) => void) {
  const qc = useQueryClient();
  const { enabled } = useKey();
  const person = useQuery({
    queryKey: ["member", memberId],
    enabled: enabled && Number.isFinite(memberId),
    queryFn: async (): Promise<DraftPerson> => {
      const a = await unwrap(api.GET("/api/members/{member_id}", { params: { path: { member_id: memberId } } }));
      return { id: a.id, name: a.display_name, line: [roleLabel(a.role), a.city].filter(Boolean).join(" · ") };
    },
  });
  const start = useMutation({
    mutationFn: async ({ text, file }: { text: string; file: File | null }) => {
      const upload_id = file ? await uploadImage(file) : null;
      return unwrap(api.POST("/api/conversations", { body: { member_id: memberId, body: text.trim(), upload_id } }));
    },
    onSuccess: (r) => { qc.invalidateQueries({ queryKey: ["inbox"] }); onStarted(r.conversation.id); },
  });
  return { person: person.data, isPending: person.isPending, isError: person.isError, start };
}
