"use client";

import { useRef, useState } from "react";
import { cx } from "./cx";
import type { MediaItem } from "./types";

/** Full-bleed images, scroll-snap with a dot pager. Frame is 4:5 or 1:1 based on the first image. */
export function MediaPager({ media, priority }: { media: MediaItem[]; priority?: boolean }) {
  const scroller = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(0);
  if (media.length === 0) return null;
  const first = media[0];
  const ratio = first.width && first.height && first.width / first.height > 0.9 ? "1 / 1" : "4 / 5";
  return (
    <div className="relative">
      <div
        ref={scroller}
        className="no-scrollbar flex snap-x snap-mandatory overflow-x-auto"
        tabIndex={media.length > 1 ? 0 : undefined}
        role={media.length > 1 ? "group" : undefined}
        aria-label={media.length > 1 ? `Images, ${media.length}` : undefined}
        onScroll={(e) => { const t = e.currentTarget; setPage(Math.round(t.scrollLeft / t.clientWidth)); }}
      >
        {media.map((m, i) => (
          <img
            key={m.src}
            src={m.src}
            srcSet={`${m.srcSmall} 480w, ${m.src} 1440w`}
            sizes="(min-width: 1024px) 600px, 100vw"
            alt={m.alt}
            width={m.width ?? undefined}
            height={m.height ?? undefined}
            loading={priority && i === 0 ? "eager" : "lazy"}
            decoding="async"
            className="w-full shrink-0 snap-center bg-surface-2 object-cover"
            style={{ aspectRatio: ratio }}
          />
        ))}
      </div>
      {media.length > 1 && (
        <div className="pointer-events-none absolute inset-x-0 bottom-3 flex justify-center gap-1.5" aria-hidden>
          {media.map((m, i) => (
            <span key={m.src} className={cx("h-1.5 w-1.5 rounded-full transition-opacity duration-150", i === page ? "bg-white opacity-100" : "bg-white opacity-50")} style={{ boxShadow: "0 0 0 1px rgba(0,0,0,.35)" }} />
          ))}
        </div>
      )}
    </div>
  );
}
