"use client";

import { ExternalLink, MoreHorizontal } from "lucide-react";
import { useState } from "react";
import { Avatar } from "./Avatar";
import { VerifiedBadge } from "./Badge";
import { Chip } from "./Chip";
import { MediaPager } from "./MediaPager";
import { ReactionBar, type ReactionKind } from "./ReactionBar";
import type { PostView } from "./types";
import { cx } from "./cx";

type Props = {
  post: PostView;
  onReact: (k: ReactionKind, on: boolean) => void;
  onMore: () => void;
  onOpenAuthor?: () => void;
  priority?: boolean;
  className?: string;
};

/** A build log. Media runs edge to edge; text shows two lines until "more". */
export function PostCard({ post, onReact, onMore, onOpenAuthor, priority, className }: Props) {
  const [open, setOpen] = useState(false);
  const long = post.body.length > 120;
  const a = post.author;
  let host = "";
  try { host = post.link ? new URL(post.link).hostname.replace(/^www\./, "") : ""; } catch { host = post.link; }
  return (
    <article className={cx("border-b border-border pb-4", className)}>
      <header className="flex items-center gap-3 px-4 py-3 lg:px-0">
        <button onClick={onOpenAuthor} className="flex min-w-0 flex-1 items-center gap-3 text-left">
          <Avatar name={a.name} src={a.photo} size={40} />
          <span className="min-w-0">
            <span className="t-body block truncate font-semibold">{a.name} <VerifiedBadge level={a.level} /></span>
            <span className="t-caption block truncate text-text-muted">{[a.headline || a.role, a.place].filter(Boolean).join(", ")} · {post.when}</span>
          </span>
        </button>
        <button onClick={onMore} aria-label="More options" className="-mr-2 flex h-11 w-11 items-center justify-center rounded-full text-text-muted lg:mr-0">
          <MoreHorizontal size={20} strokeWidth={1.75} />
        </button>
      </header>
      <div className="lg:overflow-hidden lg:rounded-card"><MediaPager media={post.media} priority={priority} /></div>
      <div className="flex flex-col gap-3 px-4 pt-3 lg:px-0">
        <p className={cx("t-body whitespace-pre-line", !open && "line-clamp-2")}>
          {post.body}
        </p>
        {long && !open && <button className="t-caption -mt-2 self-start py-2 font-semibold text-text-muted" onClick={() => setOpen(true)}>more</button>}
        {post.tags.length > 0 && (
          <div className="flex flex-wrap gap-2">{post.tags.map((t) => <Chip key={t} label={t} />)}</div>
        )}
        {post.link && (
          <a href={post.link} target="_blank" rel="noopener noreferrer nofollow" className="flex min-h-12 items-center gap-3 rounded-card border border-border px-4 py-2">
            <ExternalLink size={20} strokeWidth={1.75} className="shrink-0 text-text-muted" aria-hidden />
            <span className="t-body min-w-0 truncate">{host}</span>
          </a>
        )}
        {!post.mine && <ReactionBar active={post.reactions} onToggle={onReact} />}
      </div>
    </article>
  );
}
