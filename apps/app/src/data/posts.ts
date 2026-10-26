"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import type { PostView, ReactionKind, ReplyView } from "@circuit/ui";
import { ago } from "@/lib/format";
import { api, unwrap } from "./client";
import { useFeatures } from "./features";
import { useReact, useReport } from "./home";
import { useKey } from "./keys";
import { toPerson, toPost } from "./mappers";
import { useMe } from "./me";

/** Most characters in a reply (DESIGN.md §4 Build log). */
export const REPLY_MAX = 300;

const REACTION_WORDS: Record<ReactionKind, string> = { helpful: "found it helpful", intro_me: "asked for an intro", lets_talk: "want to talk" };

/** "Only you see this: 4 found it helpful, 2 asked for an intro, 3 replies." The author's private totals (DESIGN.md §8). */
function privateLine(s: Schemas["PrivateStatsOut"] | null | undefined): string | null {
  if (!s) return null;
  const parts = (Object.keys(REACTION_WORDS) as ReactionKind[]).filter((k) => (s.reactions[k] ?? 0) > 0).map((k) => `${s.reactions[k]} ${REACTION_WORDS[k]}`);
  if (s.replies > 0) parts.push(`${s.replies} ${s.replies === 1 ? "reply" : "replies"}`);
  return parts.length ? parts.join(", ") : "No reactions or replies yet";
}

const toReply = (r: Schemas["ReplyOut"], meId: number | undefined): ReplyView => ({
  id: r.id, author: toPerson(r.author), body: r.body, when: ago(r.created_at), mine: r.author.id === meId, replies: r.replies.map((c) => toReply(c, meId)),
});

/**
 * One build log (the post view): the post with its media pager, the viewer's reactions, and the author's private totals when it is theirs.
 * Build logs belong to the `pulse` flag: with it off the screen is a 404 (`off`).
 */
export function usePost(id: number) {
  const features = useFeatures();
  const me = useMe().data;
  const on = features.on("pulse");
  const valid = Number.isFinite(id) && id > 0;
  const { key, enabled } = useKey("post", id);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && on && valid,
    queryFn: () => unwrap(api.GET("/api/posts/{post_id}", { params: { path: { post_id: id } } })),
  });
  const post: PostView | undefined = q.data && toPost(q.data, me?.id);
  return {
    post,
    privateStats: q.data && post?.mine ? privateLine(q.data.private_stats) : null,
    off: features.ready && !on,
    isPending: !features.ready || (on && q.isPending),
    isError: q.isError,
    notFound: !valid || (q.error as { status?: number } | null)?.status === 404,
    refetch: q.refetch,
  };
}

/** Reacting on the post view: the post's own cache changes at once, and Pulse gets the same change through `useReact`. */
export function usePostReact(id: number) {
  const qc = useQueryClient();
  const { key } = useKey("post", id);
  const pulse = useReact();
  return useMutation({
    mutationFn: ({ kind, on }: { kind: ReactionKind; on: boolean }) => pulse.mutateAsync({ post: id, kind, on }),
    onMutate: ({ kind, on }) => {
      const before = qc.getQueryData<Schemas["PostOut"]>(key);
      if (before) qc.setQueryData(key, { ...before, my_reactions: on ? [...new Set([...before.my_reactions, kind])] : before.my_reactions.filter((k) => k !== kind) });
      return { before };
    },
    onError: (_e, _v, ctx) => { if (ctx?.before) qc.setQueryData(key, ctx.before); },
  });
}

/** Deletes your own build log. */
export function useDeletePost() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE("/api/posts/{post_id}", { params: { path: { post_id: id } } })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pulse"] }); qc.invalidateQueries({ queryKey: ["member-posts"] }); },
  });
}

/** Replies, threaded one level deep (oldest first), plus sending, deleting and reporting one. */
export function useReplies(postId: number, on = true) {
  const qc = useQueryClient();
  const me = useMe().data;
  const { key, enabled } = useKey("replies", postId);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && on && Number.isFinite(postId),
    queryFn: () => unwrap(api.GET("/api/posts/{post_id}/replies", { params: { path: { post_id: postId } } })),
  });
  const send = useMutation({
    mutationFn: ({ body, parentId }: { body: string; parentId: number | null }) =>
      unwrap(api.POST("/api/posts/{post_id}/replies", { params: { path: { post_id: postId } }, body: { body: body.trim(), parent_id: parentId } })),
    onSuccess: (r, { parentId }) => {
      qc.setQueryData<Schemas["ReplyOut"][]>(key, (old) => {
        if (!old) return old;
        if (parentId === null) return [...old, r];
        return old.map((x) => (x.id === parentId ? { ...x, replies: [...x.replies, r] } : x));
      });
      qc.invalidateQueries({ queryKey: ["post", postId] }); // the author's private reply count
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE("/api/replies/{reply_id}", { params: { path: { reply_id: id } } })),
    onSuccess: (_d, id) => qc.setQueryData<Schemas["ReplyOut"][]>(key, (old) => old?.filter((x) => x.id !== id).map((x) => ({ ...x, replies: x.replies.filter((c) => c.id !== id) }))),
  });
  const report = useReport();
  return {
    replies: (q.data ?? []).map((r) => toReply(r, me?.id)),
    isPending: q.isPending,
    isError: q.isError,
    refetch: q.refetch,
    send,
    remove,
    report: (id: number, reason: string) => report.mutateAsync({ target_type: "reply", target_id: id, reason }),
  };
}
