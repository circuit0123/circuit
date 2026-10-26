"use client";

import { ImagePlus, RotateCw, X } from "lucide-react";
import { useRef } from "react";
import { cx } from "./cx";

/** The two frames a build log picture can have (DESIGN.md §4 Build log): portrait 4:5 or square. */
export type MediaAspect = "4:5" | "1:1";
const RATIO: Record<MediaAspect, string> = { "4:5": "4 / 5", "1:1": "1 / 1" };

export type MediaSlotState = "processing" | "uploading" | "done" | "failed";

type SlotProps = {
  src: string;
  /** "Photo 2 of 3". */
  label: string;
  state: MediaSlotState;
  /** 0–1 while uploading. */
  progress: number;
  /** The description is still empty: the slot says so, because a build log can't be posted without it (DESIGN.md §10). */
  needsAlt: boolean;
  aspect: MediaAspect;
  /** Where the picture sits in its frame (0–1 each way), as chosen in the crop sheet. */
  focus: { x: number; y: number };
  onOpen: () => void;
  onRemove: () => void;
  onRetry: () => void;
};

/** One picture in the composer: the cropped preview, upload progress, Retry when it failed, and a remove button. Tapping it opens crop and description. */
export function MediaSlot({ src, label, state, progress, needsAlt, aspect, focus, onOpen, onRemove, onRetry }: SlotProps) {
  const pct = Math.round(progress * 100);
  return (
    <div className="relative overflow-hidden rounded-card bg-surface-2" style={{ aspectRatio: RATIO[aspect] }}>
      <button type="button" onClick={onOpen} aria-label={`${label}. ${needsAlt ? "Needs a description. " : ""}Crop or describe`} className="absolute inset-0">
        <img src={src} alt="" className="h-full w-full object-cover" style={{ objectPosition: `${focus.x * 100}% ${focus.y * 100}%` }} />
      </button>
      {state === "uploading" || state === "processing" ? (
        <div className="pointer-events-none absolute inset-x-2 bottom-2">
          <div role="progressbar" aria-label={`${label} upload`} aria-valuemin={0} aria-valuemax={100} aria-valuenow={state === "processing" ? 0 : pct} className="h-1.5 overflow-hidden rounded-full bg-black/45">
            <div className="h-full rounded-full bg-white transition-[width] duration-200" style={{ width: `${state === "processing" ? 4 : Math.max(4, pct)}%` }} />
          </div>
        </div>
      ) : null}
      {state === "failed" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/60 p-2 text-center text-white">
          <span className="t-footnote">Didn&apos;t upload</span>
          <button type="button" onClick={onRetry} className="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-white px-4 t-subhead font-semibold text-black active:opacity-80">
            <RotateCw size={16} strokeWidth={2} aria-hidden />Retry<span className="sr-only"> {label}</span>
          </button>
        </div>
      )}
      {needsAlt && state !== "failed" && (
        <span aria-hidden className="pointer-events-none absolute left-2 top-2 rounded-full bg-black/65 px-2 py-0.5 t-caption text-white">Add description</span>
      )}
      <button type="button" onClick={onRemove} aria-label={`Remove ${label}`} className="absolute right-1 top-1 flex h-11 w-11 items-center justify-center">
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-black/65 text-white"><X size={16} strokeWidth={2} aria-hidden /></span>
      </button>
    </div>
  );
}

/** The big empty area at the top of the composer (Composer.dc.html): media comes first. */
export function AddMedia({ onClick, compact, aspect = "4:5", label = "Add up to 4 photos" }: { onClick: () => void; /** A tile next to the photos, in their frame. */ compact?: boolean; aspect?: MediaAspect; label?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cx("flex w-full flex-col items-center justify-center gap-3 rounded-card text-text-muted active:opacity-80", compact ? "bg-surface-2" : "h-[300px] bg-surface")}
      style={compact ? { aspectRatio: RATIO[aspect] } : undefined}
    >
      <ImagePlus size={compact ? 24 : 32} strokeWidth={1.5} aria-hidden />
      <span className={compact ? "t-footnote" : "t-body"}>{label}</span>
    </button>
  );
}

/** "123 / 500" in mono under a text area. Read out only near the limit, so it doesn't talk over typing. */
export function CharCounter({ count, max, className }: { count: number; max: number; className?: string }) {
  const near = count >= max - 20;
  return (
    <p className={cx("num t-caption text-right", count >= max ? "text-danger" : "text-text-subtle", className)} aria-live={near ? "polite" : "off"}>
      <span className="sr-only">Characters used: </span>{count} / {max}
    </p>
  );
}

type CropProps = {
  src: string;
  aspect: MediaAspect;
  focus: { x: number; y: number };
  onChange: (focus: { x: number; y: number }) => void;
  alt?: string;
};

/**
 * Crop only, no filters (DESIGN.md §4 Build log): the picture fills the frame and you drag it (or use the arrow keys) to choose what
 * stays in. `focus` is where the frame sits across the picture, 0–1 each way; the app cuts the image to that frame before uploading.
 */
export function CropFrame({ src, aspect, focus, onChange, alt = "" }: CropProps) {
  const start = useRef<{ x: number; y: number; fx: number; fy: number; w: number; h: number } | null>(null);
  const clamp = (v: number) => Math.min(1, Math.max(0, v));
  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label="Crop. Drag the photo or use the arrow keys to choose what stays in the frame"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round((aspect === "1:1" ? focus.x : focus.y) * 100)}
      data-no-swipe
      className="relative w-full cursor-grab touch-none overflow-hidden rounded-card bg-surface-2 outline-none focus-visible:ring-2 focus-visible:ring-live active:cursor-grabbing"
      style={{ aspectRatio: RATIO[aspect] }}
      onPointerDown={(e) => {
        const r = e.currentTarget.getBoundingClientRect();
        start.current = { x: e.clientX, y: e.clientY, fx: focus.x, fy: focus.y, w: r.width, h: r.height };
        e.currentTarget.setPointerCapture(e.pointerId);
      }}
      onPointerMove={(e) => {
        const s = start.current;
        if (!s) return;
        // Dragging the picture right shows more of its left side, so the focus moves the other way.
        onChange({ x: clamp(s.fx - (e.clientX - s.x) / s.w), y: clamp(s.fy - (e.clientY - s.y) / s.h) });
      }}
      onPointerUp={() => { start.current = null; }}
      onPointerCancel={() => { start.current = null; }}
      onKeyDown={(e) => {
        const step = 0.05;
        const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
        if (!d) return;
        e.preventDefault();
        onChange({ x: clamp(focus.x + d[0]), y: clamp(focus.y + d[1]) });
      }}
    >
      <img src={src} alt={alt} draggable={false} className="pointer-events-none h-full w-full select-none object-cover" style={{ objectPosition: `${focus.x * 100}% ${focus.y * 100}%` }} />
      {/* Rule-of-thirds guide, so the frame reads as a crop and not just a picture. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 grid grid-cols-3 grid-rows-3">
        {Array.from({ length: 9 }, (_, i) => <span key={i} className="border-[0.5px] border-white/30" />)}
      </div>
    </div>
  );
}
