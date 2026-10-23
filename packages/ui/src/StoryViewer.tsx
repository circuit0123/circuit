"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Avatar } from "./Avatar";
import { VerifiedBadge } from "./Badge";
import { cx } from "./cx";
import { useOverlay } from "./overlay";
import { fade, sheetSpring } from "./theme";
import type { PostView, RoleView } from "./types";

export type Story =
  | { kind: "post"; key: string; post: PostView }
  | { kind: "role"; key: string; role: RoleView; when: string };

type Props = { open: boolean; name: string; stories: Story[]; onClose: () => void; onViewed?: () => void };

/** Full-screen. Tap right/left to move, swipe down to close. No auto-advance: nothing rushes you. */
export function StoryViewer({ open, name, stories, onClose, onViewed }: Props) {
  const reduce = useReducedMotion();
  const ref = useOverlay(open, onClose);
  const [i, setI] = useState(0);
  useEffect(() => { if (open) { setI(0); onViewed?.(); } }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const next = useCallback(() => (i + 1 >= stories.length ? onClose() : setI(i + 1)), [i, stories.length, onClose]);
  const prev = useCallback(() => setI((n) => Math.max(0, n - 1)), []);
  useEffect(() => {
    if (!open) return;
    const k = (e: KeyboardEvent) => { if (e.key === "ArrowRight") next(); if (e.key === "ArrowLeft") prev(); };
    document.addEventListener("keydown", k);
    return () => document.removeEventListener("keydown", k);
  }, [open, next, prev]);
  const s = stories[i];
  return (
    <AnimatePresence>
      {open && s && (
        <motion.div
          ref={ref}
          role="dialog"
          aria-modal="true"
          aria-label={`${name}, Today`}
          tabIndex={-1}
          className="fixed inset-0 z-50 flex flex-col bg-bg outline-none lg:items-center lg:bg-black/80"
          initial={reduce ? { opacity: 0 } : { y: "100%" }}
          animate={reduce ? { opacity: 1 } : { y: 0 }}
          exit={reduce ? { opacity: 0 } : { y: "100%" }}
          transition={reduce ? fade : sheetSpring}
          drag={reduce ? false : "y"}
          dragConstraints={{ top: 0, bottom: 0 }}
          dragElastic={{ top: 0, bottom: 0.7 }}
          onDragEnd={(_, d) => { if (d.offset.y > 140 || d.velocity.y > 700) onClose(); }}
        >
          <div className="relative flex min-h-0 w-full flex-1 flex-col bg-bg lg:max-w-[460px]">
            <div className="flex gap-1 px-3 pt-3" aria-hidden>
              {stories.map((st, n) => (
                <span key={st.key} className={cx("h-0.5 flex-1 rounded-full", n <= i ? "bg-text" : "bg-border")} />
              ))}
            </div>
            <div className="flex items-center gap-3 px-4 py-3">
              {s.kind === "post" ? (
                <>
                  <Avatar name={s.post.author.name} src={s.post.author.photo} size={40} />
                  <div className="min-w-0 flex-1">
                    <p className="t-body truncate font-semibold">{s.post.author.name} <VerifiedBadge level={s.post.author.level} /></p>
                    <p className="t-caption truncate text-text-muted">{s.post.when} ago</p>
                  </div>
                </>
              ) : (
                <>
                  <Avatar name={name} size={40} />
                  <div className="min-w-0 flex-1">
                    <p className="t-body truncate font-semibold">{name}</p>
                    <p className="t-caption truncate text-text-muted">Posted a role, {s.when} ago</p>
                  </div>
                </>
              )}
              <button onClick={onClose} aria-label="Close" className="relative z-10 flex h-11 w-11 items-center justify-center rounded-full text-text">
                <X size={24} strokeWidth={1.75} />
              </button>
            </div>
            <div className="relative min-h-0 flex-1">
              <AnimatePresence mode="wait" initial={false}>
                <motion.div key={s.key} className="absolute inset-0 flex flex-col overflow-y-auto" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={fade}>
                  {s.kind === "post" ? <PostSlide post={s.post} /> : <RoleSlide role={s.role} />}
                </motion.div>
              </AnimatePresence>
              <button aria-label="Previous" onClick={prev} disabled={i === 0} className="absolute inset-y-0 left-0 w-1/3" />
              <button aria-label="Next" onClick={next} className="absolute inset-y-0 right-0 w-2/3" />
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function PostSlide({ post }: { post: PostView }) {
  const m = post.media[0];
  return (
    <>
      {m && <img src={m.src} srcSet={`${m.srcSmall} 480w, ${m.src} 1440w`} sizes="(min-width: 1024px) 460px, 100vw" alt={m.alt} className="w-full object-cover" style={{ aspectRatio: "4 / 5", maxHeight: "70dvh" }} />}
      <div className="px-4 py-4">
        <p className="t-body whitespace-pre-line">{post.body}</p>
      </div>
    </>
  );
}

function RoleSlide({ role }: { role: RoleView }) {
  return (
    <div className="flex flex-1 flex-col justify-center gap-3 px-6">
      <p className="t-caption text-text-muted">{role.startup}</p>
      <h2 className="t-display">{role.title}</h2>
      <p className="t-body text-text-muted">{role.place}{role.stipend && <> · <span className="num">{role.stipend}</span></>}</p>
    </div>
  );
}
