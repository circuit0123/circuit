"use client";

import { animate, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { cx } from "./cx";
import { initials, toneFor } from "./theme";

export type RingState = "none" | "unseen" | "seen";
const SIZES = { 32: "t-micro", 40: "t-caption", 64: "t-headline", 96: "t-title", 128: "t-display" } as const;
export type AvatarSize = keyof typeof SIZES;

type Props = {
  name: string;
  src?: string | null;
  size?: AvatarSize;
  ring?: RingState;
  className?: string;
};

/** Initials on a name-derived tone when there is no photo; never a silhouette. */
export function Avatar({ name, src, size = 40, ring = "none", className }: Props) {
  const tone = toneFor(name);
  const inner = (
    <span
      className={cx("flex h-full w-full items-center justify-center overflow-hidden rounded-full font-semibold", SIZES[size])}
      style={{ background: tone.bg, color: tone.fg }}
      aria-hidden
    >
      {src ? <img src={src} alt="" className="h-full w-full object-cover" /> : initials(name)}
    </span>
  );
  if (ring === "none") {
    return (
      <span className={cx("inline-flex shrink-0", className)} style={{ width: size, height: size }}>
        {inner}
      </span>
    );
  }
  return <RingedAvatar ring={ring} size={size} className={className}>{inner}</RingedAvatar>;
}

/** Unseen = signature gradient. Seen = thin neutral ring; the gradient fades out over 400ms. */
function RingedAvatar({ ring, size, className, children }: { ring: RingState; size: number; className?: string; children: React.ReactNode }) {
  const reduce = useReducedMotion();
  const gradient = useRef<HTMLSpanElement>(null);
  const first = useRef(true);
  useEffect(() => {
    const el = gradient.current;
    if (!el) return;
    const target = ring === "unseen" ? 1 : 0;
    if (first.current || reduce) {
      el.style.opacity = String(target);
    } else {
      animate(el, { opacity: target }, { duration: 0.4 });
    }
    first.current = false;
  }, [ring, reduce]);
  const pad = size >= 64 ? 3 : 2;
  return (
    <span className={cx("relative inline-flex shrink-0 rounded-full", className)} style={{ width: size, height: size }}>
      <span className="absolute inset-0 rounded-full border border-border" aria-hidden />
      <span ref={gradient} className="ring-signature absolute inset-0 rounded-full" style={{ opacity: ring === "unseen" ? 1 : 0 }} aria-hidden />
      <span className="absolute rounded-full bg-bg" style={{ inset: pad }} aria-hidden />
      <span className="absolute" style={{ inset: pad + 2 }}>{children}</span>
    </span>
  );
}
