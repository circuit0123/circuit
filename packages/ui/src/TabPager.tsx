"use client";

import { animate, useMotionValue, useReducedMotion, type MotionValue } from "motion/react";
import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { spring } from "./theme";

export type PagerTab = { id: string; node: React.ReactNode };

type Props = {
  /** Visible tabs in bar order. Swipe order follows this list, so a tab that is off simply isn't here. */
  tabs: PagerTab[];
  /** The active tab, or null while a pushed (non-tab) screen is showing; panes stay mounted underneath. */
  value: string | null;
  /** Called after a swipe commits. The app navigates; the pager has already moved. */
  onSwipe: (id: string) => void;
  /** Settings -> Appearance -> "Swipe between tabs". */
  swipe: boolean;
  /** Fractional index of the shown tab. The tab bar's indicator reads it, so it slides with the finger. */
  progress: MotionValue<number>;
  className?: string;
};

const COMMIT_FRACTION = 0.35;
const COMMIT_VELOCITY = 600;
const MAX_ANGLE_TAN = Math.tan((30 * Math.PI) / 180);

/** True when a gesture that starts here belongs to something else: a swipeable list, the map, a chips row, a segmented control. */
function ownsHorizontalSwipe(start: EventTarget | null, root: HTMLElement): boolean {
  let el = start instanceof HTMLElement ? start : null;
  while (el && el !== root) {
    if (el.dataset.noSwipe !== undefined) return true;
    const s = getComputedStyle(el);
    if ((s.overflowX === "auto" || s.overflowX === "scroll") && el.scrollWidth > el.clientWidth + 1) return true;
    el = el.parentElement;
  }
  return false;
}

let locks = 0;
/**
 * A screen calls this while its own gestures need the whole surface (Discover's Map segment: the map owns every gesture there).
 * Tab swiping is off for as long as any caller says `locked`.
 */
export function useTabSwipeLock(locked = true) {
  useEffect(() => {
    if (!locked) return;
    locks += 1;
    return () => { locks -= 1; };
  }, [locked]);
}

/** A sheet, a menu or the on-screen keyboard is open, or a text field has focus: a sideways drag belongs to them (DESIGN.md §3). */
const overlayOpen = () =>
  locks > 0 ||
  !!document.querySelector('[aria-modal="true"], [role="menu"]') ||
  !!document.activeElement?.matches("input, textarea, select, [contenteditable=\"true\"]") ||
  (window.visualViewport ? window.visualViewport.height < window.innerHeight - 120 : false);

type Drag = {
  state: "pending" | "drag" | "ignore" | "settling";
  x0: number; y0: number; vx: number; lastX: number; lastT: number;
  from: number; to: number; dir: -1 | 1; width: number; pane: HTMLElement | null; inner: HTMLElement | null;
};

/**
 * Swipeable tabs (DESIGN.md §3). The screen follows the finger 1:1; release past 35% of the width
 * or above 600px/s to commit, otherwise it snaps back. Every tab stays mounted once visited and
 * keeps its scroll position. A swipe starts only when it is clearly horizontal (under 30 degrees)
 * and does not begin inside something that scrolls sideways or is marked data-no-swipe.
 * The neighbouring pane is already mounted, so there is no blank frame.
 */
export function TabPager({ tabs, value, onSwipe, swipe, progress, className }: Props) {
  const reduce = useReducedMotion();
  const rootRef = useRef<HTMLDivElement>(null);
  const panes = useRef(new Map<string, HTMLElement>());
  const scrolls = useRef(new Map<string, number>());
  const drag = useRef<Drag | null>(null);
  const x = useMotionValue(0);

  const [shown, setShown] = useState(value);
  const [visited, setVisited] = useState<string[]>(() => (value ? [value] : []));
  const ids = tabs.map((t) => t.id);

  // Follow the app (tab taps, deep links, back button). State derived from props during render, as React recommends.
  const [seenValue, setSeenValue] = useState(value);
  if (value !== seenValue) { setSeenValue(value); setShown(value); }
  // Mount the active tab and its neighbours, and keep every tab that has been seen.
  const at = shown ? ids.indexOf(shown) : -1;
  const wanted = at >= 0 ? [shown!, ids[at - 1], ids[at + 1]].filter(Boolean) : [];
  const missing = wanted.filter((id) => !visited.includes(id));
  if (missing.length) setVisited((v) => [...v, ...missing.filter((id) => !v.includes(id))]);

  // Remember each tab's scroll position while it is the one showing.
  useEffect(() => {
    const onScroll = () => { if (shown && !drag.current?.pane) scrolls.current.set(shown, window.scrollY); };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [shown]);

  // Slide the tab bar indicator to the shown tab, and restore that tab's scroll and entrance motion.
  const prev = useRef<string | null>(shown);
  const swiped = useRef(false);
  useLayoutEffect(() => {
    const i = shown ? ids.indexOf(shown) : -1;
    if (i >= 0 && !drag.current?.pane) animate(progress, i, reduce ? { duration: 0 } : spring);
    finish();
    if (shown && prev.current !== shown) {
      const was = prev.current ? ids.indexOf(prev.current) : -1;
      const saved = scrolls.current.get(shown) ?? 0;
      window.scrollTo(0, saved);
      const el = panes.current.get(shown);
      if (el && !swiped.current && was >= 0 && i >= 0) {
        const dirn = i > was ? 1 : -1;
        animate(el, reduce ? { opacity: [0, 1] } : { opacity: [0, 1], transform: [`translateX(${dirn * 24}px)`, "translateX(0px)"] }, reduce ? { duration: 0.15 } : { duration: 0.3, ease: [0.2, 0, 0, 1] });
      }
    }
    swiped.current = false;
    prev.current = shown;
  }, [shown]); // eslint-disable-line react-hooks/exhaustive-deps

  const finish = useCallback(() => {
    const d = drag.current;
    if (!d) return;
    for (const el of panes.current.values()) { el.style.transform = ""; el.style.display = ""; el.style.position = ""; el.style.inset = ""; el.style.width = ""; el.style.height = ""; el.style.overflow = ""; el.style.zIndex = ""; el.style.touchAction = ""; }
    if (d.inner) d.inner.style.transform = "";
    drag.current = null;
    x.set(0);
  }, [x]);

  // Paint a drag: the shown pane moves with the finger, its neighbour comes in beside it.
  useEffect(() => {
    return x.on("change", (dx) => {
      const d = drag.current;
      if (!d || !shown) return;
      const cur = panes.current.get(shown);
      if (cur) cur.style.transform = `translate3d(${dx}px,0,0)`;
      if (d.pane) d.pane.style.transform = `translate3d(${dx + d.dir * d.width}px,0,0)`;
      progress.set(Math.min(ids.length - 1, Math.max(0, ids.indexOf(shown) - dx / d.width)));
    });
  }, [x, progress, shown, ids.length]); // eslint-disable-line react-hooks/exhaustive-deps

  const enabled = swipe && !reduce;

  const down = (e: React.PointerEvent) => {
    if (!enabled || !shown || e.pointerType === "mouse" || !e.isPrimary || drag.current) return;
    if (e.clientX < 24 || overlayOpen() || !rootRef.current || ownsHorizontalSwipe(e.target, rootRef.current)) return;
    drag.current = { state: "pending", x0: e.clientX, y0: e.clientY, vx: 0, lastX: e.clientX, lastT: e.timeStamp, from: ids.indexOf(shown), to: -1, dir: 1, width: rootRef.current.clientWidth, pane: null, inner: null };
  };

  const move = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d || d.state === "ignore" || d.state === "settling" || !shown) return;
    const dx = e.clientX - d.x0;
    const dy = e.clientY - d.y0;
    if (d.state === "pending") {
      if (Math.abs(dx) < 10 && Math.abs(dy) < 10) return;
      if (Math.abs(dy) > Math.abs(dx) * MAX_ANGLE_TAN) { d.state = "ignore"; return; }
      d.state = "drag";
      d.dir = dx < 0 ? 1 : -1; // swiping left shows the next tab
      d.to = d.from + d.dir;
      const nid = ids[d.to];
      const el = nid ? panes.current.get(nid) : undefined;
      if (el) {
        d.pane = el;
        d.inner = el.firstElementChild as HTMLElement | null;
        Object.assign(el.style, { display: "block", position: "fixed", inset: "0", width: "100%", height: "100dvh", overflow: "hidden", zIndex: "1" });
        if (d.inner) d.inner.style.transform = `translateY(${-(scrolls.current.get(nid!) ?? 0)}px)`;
      }
      rootRef.current?.setPointerCapture(e.pointerId);
    }
    const dt = Math.max(1, e.timeStamp - d.lastT);
    d.vx = 0.8 * d.vx + 0.2 * ((e.clientX - d.lastX) / dt) * 1000;
    d.lastX = e.clientX; d.lastT = e.timeStamp;
    // No neighbour that way: let it stretch a little, then resist.
    x.set(d.pane ? dx : dx * 0.25);
  };

  const up = (e: React.PointerEvent) => {
    const d = drag.current;
    if (!d) return;
    if (d.state !== "drag") { drag.current = null; return; }
    rootRef.current?.releasePointerCapture?.(e.pointerId);
    const dx = x.get();
    const goes = !!d.pane && (Math.abs(dx) / d.width > COMMIT_FRACTION || (Math.abs(d.vx) > COMMIT_VELOCITY && Math.sign(d.vx) === Math.sign(dx)));
    d.state = "settling";
    animate(x, goes ? -d.dir * d.width : 0, {
      ...spring,
      onComplete: () => {
        if (goes) {
          const id = ids[d.to];
          swiped.current = true;
          setShown(id);
          onSwipe(id);
          // `finish` runs in the layout effect once the new pane is the shown one (no flash of the old one).
        } else finish();
      },
    });
  };

  const cancel = () => { if (drag.current?.state === "drag") { drag.current.state = "settling"; animate(x, 0, { ...spring, onComplete: finish }); } else drag.current = null; };

  return (
    <div ref={rootRef} className={className} style={{ touchAction: enabled ? "pan-y" : undefined }} onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerCancel={cancel}>
      {tabs.map((t) =>
        visited.includes(t.id) || wanted.includes(t.id) ? (
          <div key={t.id} data-pane={t.id} hidden={t.id !== shown} ref={(el) => { if (el) panes.current.set(t.id, el); else panes.current.delete(t.id); }}>
            <div>{t.node}</div>
          </div>
        ) : null,
      )}
    </div>
  );
}
