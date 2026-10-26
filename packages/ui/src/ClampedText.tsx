"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { cx } from "./cx";

/**
 * Body text that shows its first `lines` full lines, then a "more" button (DESIGN.md §5 "Line length"). It is cut at a line
 * boundary, never with an ellipsis, so it can't end on "You have a…". Reasons are short and are shown whole, not through this.
 */
export function ClampedText({ text, lines = 2, className }: { text: string; lines?: number; className?: string }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [open, setOpen] = useState(false);
  const [cut, setCut] = useState(false);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el || open) return;
    const measure = () => setCut(el.scrollHeight > el.clientHeight + 1);
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [text, open]);
  return (
    <>
      <p ref={ref} className={cx("t-body max-w-[540px] whitespace-pre-line", className)} style={open ? undefined : { maxHeight: `${lines * 1.4}em`, overflow: "hidden" }}>
        {text}
      </p>
      {cut && !open && (
        <button type="button" className="t-subhead -mt-1 self-start py-2 font-semibold text-text-muted" onClick={() => setOpen(true)}>
          more
        </button>
      )}
    </>
  );
}
