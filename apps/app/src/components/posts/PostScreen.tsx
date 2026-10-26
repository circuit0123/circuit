"use client";

import { ArrowUp, MoreHorizontal, X } from "lucide-react";
import { BarButton, Button, CharCounter, EmptyState, ErrorState, PostCard, PushScreen, ReplyThread, Section, Sheet, Skeleton, firstName, useToast, type ReactionKind, type ReplyView } from "@circuit/ui";
import { notFound, useRouter } from "next/navigation";
import { useState } from "react";
import { REPLY_MAX, loadFailed, memberHref, newMessageHref, useDeletePost, useHome, usePost, usePostReact, useReplies, useReport } from "@/data";
import { useAskIntro } from "../home/IntroSheet";
import { goBack } from "../jobs/JobScreen";
import { ConfirmSheet, ReportSheet } from "../sheets";

/**
 * One build log (DESIGN.md §4 Build log): the post with its media pager, reactions with no public counts (the author sees their own totals,
 * privately), replies one level deep, and Report (or Delete for your own). Build logs belong to the `pulse` flag: with it off this is a 404.
 */
export function PostScreen({ id }: { id: number }) {
  const router = useRouter();
  const toast = useToast();
  const q = usePost(id);
  const post = q.post;
  const react = usePostReact(id);
  const report = useReport();
  const del = useDeletePost();
  const replies = useReplies(id, !!post);
  const ask = useAskIntro();
  const { minor } = useHome();
  const [sheet, setSheet] = useState<null | "menu" | "report" | "delete">(null);
  const [replyMenu, setReplyMenu] = useState<ReplyView | null>(null);
  const [replyReport, setReplyReport] = useState<ReplyView | null>(null);
  const [replyTo, setReplyTo] = useState<ReplyView | null>(null);
  if (q.off || q.notFound) notFound();

  const onReact = (kind: ReactionKind, on: boolean) => {
    if (!post) return;
    const save = () => react.mutate({ kind, on }, { onError: () => toast({ text: "Couldn't save that. Try again.", tone: "error" }) });
    // "Intro me" opens the intro sheet and "Let's talk" the message flow (DESIGN.md §4); the reaction is saved with them.
    if (on && kind === "intro_me") ask({ id: post.author.id, name: post.author.name }, save);
    else if (on && kind === "lets_talk") { save(); router.push(newMessageHref(post.author.id)); }
    else save();
  };

  return (
    <PushScreen
      title="Build log"
      onBack={() => goBack(router, "/")}
      right={post && <BarButton label="More options" onClick={() => setSheet(post.mine ? "delete" : "menu")}><MoreHorizontal size={22} strokeWidth={1.75} /></BarButton>}
      bleed
      footer={post && <ReplyBox to={replyTo} onCancel={() => setReplyTo(null)} busy={replies.send.isPending} onSend={async (body) => {
        try { await replies.send.mutateAsync({ body, parentId: replyTo?.id ?? null }); setReplyTo(null); return true; }
        catch { toast({ text: "Couldn't send your reply. Try again.", tone: "error" }); return false; }
      }} />}
    >
      {q.isPending && (
        <div className="flex flex-col gap-4 px-4 lg:px-0" aria-label="Loading build log">
          <div className="flex items-center gap-3" aria-hidden><Skeleton round className="h-10 w-10" /><Skeleton className="h-4 w-40" /></div>
          <Skeleton className="aspect-[4/5] w-full" />
        </div>
      )}
      {q.isError && !q.notFound && <ErrorState className="px-4 pt-6 lg:px-0" text={loadFailed("this build log")} onRetry={() => void q.refetch()} />}
      {post && (
        <>
          <h1 className="sr-only">Build log by {post.author.name}</h1>
          <PostCard
            post={post}
            priority
            onReact={onReact}
            onMore={() => setSheet(post.mine ? "delete" : "menu")}
            onOpenAuthor={post.mine ? () => router.push("/profile") : () => router.push(memberHref(post.author.id)!)}
            hideReactions={minor ? ["intro_me"] : undefined}
          />
          {q.privateStats && <p className="t-footnote mt-3 px-4 text-text-muted lg:px-0">Only you see this: {q.privateStats}.</p>}

          <Section title="Replies">
            {replies.isPending ? (
              <div className="flex flex-col gap-3" aria-hidden><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
            ) : replies.isError ? (
              <ErrorState text={loadFailed("replies")} onRetry={() => void replies.refetch()} />
            ) : replies.replies.length === 0 ? (
              <EmptyState text={post.mine ? "No replies yet." : `No replies yet. Ask ${firstName(post.author.name)} something about it.`} />
            ) : (
              <ReplyThread
                replies={replies.replies}
                onReply={(r) => setReplyTo(r)}
                onMore={(r) => setReplyMenu(r)}
                onOpenAuthor={(aid) => router.push(memberHref(aid)!)}
              />
            )}
          </Section>

          <Sheet open={sheet === "menu"} onClose={() => setSheet(null)} title="Build log" detents={["medium"]}>
            <Button className="w-full" onClick={() => setSheet("report")}>Report this build log</Button>
          </Sheet>
          <ReportSheet
            open={sheet === "report"}
            onClose={() => setSheet(null)}
            title="Report this build log?"
            intro="We'll look at it within a day. The author won't know who reported it."
            onSend={(reason) => report.mutateAsync({ target_type: "post", target_id: post.id, reason })}
          />
          <ConfirmSheet
            open={sheet === "delete"}
            onClose={() => setSheet(null)}
            title="Delete this build log?"
            text="It disappears from your profile and from Pulse, with its replies. This can't be undone."
            confirmLabel="Delete build log"
            busy={del.isPending}
            onConfirm={() => del.mutate(post.id, {
              onSuccess: () => { setSheet(null); toast({ text: "Build log deleted." }); router.replace("/profile"); },
              onError: () => toast({ text: "Couldn't delete it. Try again.", tone: "error" }),
            })}
          />

          <Sheet open={replyMenu !== null} onClose={() => setReplyMenu(null)} title="Reply" detents={["medium"]}>
            {replyMenu?.mine ? (
              <Button variant="destructive" className="w-full" onClick={() => {
                const r = replyMenu;
                setReplyMenu(null);
                replies.remove.mutate(r.id, { onSuccess: () => toast({ text: "Reply deleted." }), onError: () => toast({ text: "Couldn't delete it. Try again.", tone: "error" }) });
              }}>Delete reply</Button>
            ) : (
              <Button className="w-full" onClick={() => { setReplyReport(replyMenu); setReplyMenu(null); }}>Report this reply</Button>
            )}
          </Sheet>
          <ReportSheet
            open={replyReport !== null}
            onClose={() => setReplyReport(null)}
            title="Report this reply?"
            intro="We'll look at it within a day."
            onSend={(reason) => replies.report(replyReport!.id, reason)}
          />
        </>
      )}
    </PushScreen>
  );
}

/** "Add a reply" pinned to the bottom: 300 characters at most, a counter near the end, and who you're answering when it's a reply to a reply. */
function ReplyBox({ to, onCancel, onSend, busy }: { to: ReplyView | null; onCancel: () => void; onSend: (body: string) => Promise<boolean>; busy: boolean }) {
  const [text, setText] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || busy) return;
    if (await onSend(text)) setText("");
  };
  return (
    <form onSubmit={submit} aria-label="Reply">
      {to && (
        <p className="t-footnote mb-2 flex items-center gap-1 text-text-muted">
          Replying to {to.author.name}
          <button type="button" onClick={onCancel} aria-label="Stop replying to this reply" className="-my-2 flex h-11 w-11 items-center justify-center"><X size={16} strokeWidth={2} aria-hidden /></button>
        </p>
      )}
      <div className="flex items-center gap-2">
        <label className="flex h-11 min-w-0 flex-1 items-center rounded-full bg-surface-2 px-4 focus-within:ring-2 focus-within:ring-live">
          <span className="sr-only">Add a reply</span>
          <input value={text} onChange={(e) => setText(e.target.value.slice(0, REPLY_MAX))} maxLength={REPLY_MAX} placeholder={to ? `Reply to ${firstName(to.author.name)}` : "Add a reply"} className="t-body min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text-subtle" />
        </label>
        <button type="submit" aria-label="Send reply" disabled={!text.trim() || busy} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary transition-transform active:scale-[0.97] disabled:opacity-50">
          <ArrowUp size={20} strokeWidth={2.2} aria-hidden />
        </button>
      </div>
      {text.length >= REPLY_MAX - 40 && <CharCounter count={text.length} max={REPLY_MAX} className="mt-1" />}
    </form>
  );
}
