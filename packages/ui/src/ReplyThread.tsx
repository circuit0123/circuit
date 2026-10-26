"use client";

import { MoreHorizontal } from "lucide-react";
import { Avatar } from "./Avatar";
import { VerifiedBadge } from "./Badge";
import { cx } from "./cx";
import type { Person } from "./types";

export type ReplyView = {
  id: number;
  author: Person;
  body: string;
  /** Short relative time, "2h". */
  when: string;
  mine: boolean;
  /** One level only (DESIGN.md §4 Build log): replies to a reply are never nested further. */
  replies: ReplyView[];
};

type Props = {
  replies: ReplyView[];
  /** "Reply" under a top-level reply. Leave out to hide it (signed out, or replies closed). */
  onReply?: (r: ReplyView) => void;
  /** The "…" on each reply: Report, or Delete for your own. */
  onMore: (r: ReplyView) => void;
  onOpenAuthor?: (id: number) => void;
  className?: string;
};

/** Replies under a build log, threaded one level deep. No counts anywhere (DESIGN.md §8); the author's totals live on the post. */
export function ReplyThread({ replies, onReply, onMore, onOpenAuthor, className }: Props) {
  return (
    <ul className={cx("flex flex-col gap-5", className)} aria-label="Replies">
      {replies.map((r) => (
        <li key={r.id} className="flex flex-col gap-4">
          <Reply r={r} onReply={onReply} onMore={onMore} onOpenAuthor={onOpenAuthor} />
          {r.replies.length > 0 && (
            <ul className="ml-11 flex flex-col gap-4" aria-label={`Replies to ${r.author.name}`}>
              {r.replies.map((c) => <li key={c.id}><Reply r={c} onMore={onMore} onOpenAuthor={onOpenAuthor} /></li>)}
            </ul>
          )}
        </li>
      ))}
    </ul>
  );
}

function Reply({ r, onReply, onMore, onOpenAuthor }: { r: ReplyView; onReply?: (r: ReplyView) => void; onMore: (r: ReplyView) => void; onOpenAuthor?: (id: number) => void }) {
  const a = r.author;
  return (
    <article className="flex gap-3" aria-label={`${a.name}, ${r.when}`}>
      <button type="button" onClick={() => onOpenAuthor?.(a.id)} disabled={!onOpenAuthor} aria-label={a.name} className="shrink-0 self-start">
        <Avatar id={a.id} name={a.name} src={a.photo} size={32} />
      </button>
      <div className="min-w-0 flex-1">
        <p className="t-subhead">
          <span className="font-semibold">{a.name}</span> <VerifiedBadge level={a.level} /> <span className="text-text-muted">· {r.when}</span>
        </p>
        <p className="t-body mt-0.5 whitespace-pre-line break-words">{r.body}</p>
        {onReply && (
          <button type="button" onClick={() => onReply(r)} className="-ml-1 min-h-11 px-1 t-subhead font-semibold text-text-muted active:opacity-80">
            Reply<span className="sr-only"> to {a.name}</span>
          </button>
        )}
      </div>
      <button type="button" onClick={() => onMore(r)} aria-label={`More options for ${a.name}'s reply`} className="-mr-2 flex h-11 w-11 shrink-0 items-center justify-center self-start rounded-full text-text-muted">
        <MoreHorizontal size={20} strokeWidth={1.75} />
      </button>
    </article>
  );
}
