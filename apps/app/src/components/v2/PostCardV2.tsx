"use client";

import { Avatar, ClampedText, MediaPager, ReactionBar, VerifiedBadge, type PostView, type ReactionKind } from "@circuit/ui";
import { ExternalLink, MoreHorizontal } from "lucide-react";

type Props = {
  post: PostView;
  onReact: (k: ReactionKind, on: boolean) => void;
  onMore: () => void;
  onOpenAuthor?: () => void;
  hideReactions?: ReactionKind[];
};

/** A build log as a v2 card: grey card, 1px border, 22px radius. Same data and behaviour as PostCard. */
export function PostCardV2({ post, onReact, onMore, onOpenAuthor, hideReactions }: Props) {
  const a = post.author;
  let host = "";
  try { host = post.link ? new URL(post.link).hostname.replace(/^www\./, "") : ""; } catch { host = post.link; }
  return (
    <article className="overflow-hidden rounded-[22px] border border-c-border bg-c-card">
      <header className="flex items-center gap-3 p-4 pb-3">
        <button type="button" onClick={onOpenAuthor} disabled={!onOpenAuthor} className="flex min-w-0 flex-1 items-center gap-3 text-left">
          <Avatar id={a.id} name={a.name} src={a.photo} size={40} />
          <span className="min-w-0">
            <span className="block truncate text-[16px] font-semibold tracking-[-0.02em]">{a.name} <VerifiedBadge level={a.level} /></span>
            <span className="block truncate text-[13px] text-c-muted">{[a.headline || a.role, a.place].filter(Boolean).join(", ")} · {post.when}</span>
          </span>
        </button>
        <button type="button" onClick={onMore} aria-label="More options" className="-mr-2 flex h-11 w-11 items-center justify-center rounded-full text-c-muted">
          <MoreHorizontal size={20} strokeWidth={1.75} aria-hidden />
        </button>
      </header>
      <MediaPager media={post.media} priority={false} />
      <div className="flex flex-col gap-3 p-4 empty:hidden">
        <ClampedText text={post.body} />
        {post.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {post.tags.map((t) => <span key={t} className="inline-flex h-7 items-center rounded-full bg-c-bright-bg px-3 text-[12px] font-semibold text-c-bright">{t}</span>)}
          </div>
        )}
        {post.link && (
          <a href={post.link} target="_blank" rel="noopener noreferrer nofollow" className="flex min-h-12 items-center gap-3 rounded-[14px] border border-c-border bg-c-bg px-4 py-2">
            <ExternalLink size={18} strokeWidth={1.75} className="shrink-0 text-c-muted" aria-hidden />
            <span className="min-w-0 break-all text-[15px]">{host}</span>
          </a>
        )}
      </div>
      {!post.mine && <div className="border-t border-c-border px-4"><ReactionBar active={post.reactions} onToggle={onReact} hide={hideReactions} /></div>}
    </article>
  );
}
