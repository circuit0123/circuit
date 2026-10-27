"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { animate } from "motion/mini";
import { hover, inView, press, spring } from "motion";

/**
 * Landing site motion (DESIGN.md §7), switched on once the page has loaded. Renders nothing.
 * The server HTML is complete and readable; this only adds movement on top. Rules: transform and opacity only,
 * everything plays once, nothing moves the layout, and with prefers-reduced-motion nothing is touched at all.
 * (The hero headline is plain CSS in globals.css, so it starts at first paint without waiting for this code.)
 */

/** The default spring of DESIGN.md §7. `motion/mini` needs the spring generator itself: the string "spring" is rejected in development and silently turned into a plain ease-out in production. */
const SPRING = { type: spring, duration: 0.35, bounce: 0 } as const;
const RISE = 12;
const REVEAL_STAGGER = 0.04;
const REVEAL_STAGGERED = 6;

type Stop = () => void;

/** The things a section reveals: its direct children, with a list (`data-stagger`) replaced by its own items. */
function itemsOf(box: Element): HTMLElement[] {
  return Array.from(box.children).flatMap((child) => {
    const list = child.matches("[data-stagger]") ? child : child.querySelector("[data-stagger]");
    if (!list) return [child as HTMLElement];
    // `li` that use display: contents have no box to move; their one child is the card.
    return Array.from(list.children).map((li) => (getComputedStyle(li).display === "contents" ? li.firstElementChild : li) as HTMLElement);
  });
}

/** Sections below the fold fade and rise 12px when they come into view, once. Anything already on screen is never hidden. */
function reveals(): Stop[] {
  const stops: Stop[] = [];
  document.querySelectorAll("main > section:not(:first-child)").forEach((section) => {
    const box = section.firstElementChild;
    if (!box || box.getBoundingClientRect().top < window.innerHeight) return;
    const items = itemsOf(box);
    for (const el of items) {
      el.style.opacity = "0";
      el.style.transform = `translateY(${RISE}px)`;
    }
    const stop = inView(box, () => {
      stop();
      items.forEach((el, i) => {
        animate(el, { opacity: [0, 1], transform: [`translateY(${RISE}px)`, "none"] }, { ...SPRING, delay: Math.min(i, REVEAL_STAGGERED - 1) * REVEAL_STAGGER }).then(() => {
          el.style.opacity = "";
          el.style.transform = "";
        });
      });
    }, { amount: 0.1 });
    stops.push(stop);
  });
  return stops;
}

/** Audience tiles: hover or keyboard focus lifts 2px and nudges the arrow 4px; press scales to 0.98. */
function tiles(): Stop[] {
  const stops: Stop[] = [];
  document.querySelectorAll<HTMLElement>("[data-tile]").forEach((tile) => {
    const arrow = tile.querySelector<HTMLElement>("[data-arrow]");
    let hovered = false;
    let focused = false;
    let pressed = false;
    const render = () => {
      const lifted = hovered || focused;
      animate(tile, { transform: `translateY(${lifted ? -2 : 0}px) scale(${pressed ? 0.98 : 1})` }, SPRING);
      if (arrow) animate(arrow, { transform: `translateX(${lifted ? 4 : 0}px)` }, SPRING);
    };
    const onFocus = () => { focused = tile.matches(":focus-visible"); render(); };
    const onBlur = () => { focused = false; render(); };
    tile.addEventListener("focusin", onFocus);
    tile.addEventListener("focusout", onBlur);
    stops.push(
      hover(tile, () => { hovered = true; render(); return () => { hovered = false; render(); }; }),
      press(tile, () => { pressed = true; render(); return () => { pressed = false; render(); }; }),
      () => { tile.removeEventListener("focusin", onFocus); tile.removeEventListener("focusout", onBlur); },
    );
  });
  return stops;
}

/** Buttons and button-like links (not the tiles, which press themselves) scale to 0.97 while pressed. */
function buttons(): Stop[] {
  return [
    press("a[data-press]:not([data-tile]), button", (el) => {
      if (el.matches(":disabled")) return;
      animate(el, { transform: "scale(0.97)" }, SPRING);
      return () => { animate(el, { transform: "scale(1)" }, SPRING); };
    }),
  ];
}

/**
 * FAQ: the answer fades in and rises 8px as the item opens, and fades out before it closes; the + turns to × (CSS, in Faq.tsx).
 * The height changes at once, because height is not one of the three properties we animate.
 */
function faq(): Stop[] {
  const stops: Stop[] = [];
  document.querySelectorAll<HTMLDetailsElement>("details[data-faq]").forEach((details) => {
    const summary = details.querySelector("summary");
    const answer = details.querySelector<HTMLElement>("[data-faq-answer]");
    const plus = details.querySelector<HTMLElement>("[data-faq-plus]");
    if (!summary || !answer) return;
    let closing = false;
    const onClick = (e: Event) => {
      e.preventDefault();
      if (closing) return;
      if (!details.open) {
        details.open = true;
        animate(answer, { opacity: [0, 1], transform: ["translateY(8px)", "none"] }, SPRING).then(() => {
          answer.style.opacity = "";
          answer.style.transform = "";
        });
        return;
      }
      closing = true;
      if (plus) plus.style.rotate = "0deg";
      animate(answer, { opacity: 0 }, { duration: 0.15, ease: "easeOut" }).then(() => {
        details.open = false;
        answer.style.opacity = "";
        answer.style.transform = "";
        if (plus) plus.style.rotate = "";
        closing = false;
      });
    };
    summary.addEventListener("click", onClick);
    stops.push(() => summary.removeEventListener("click", onClick));
  });
  return stops;
}

export function LandingMotion() {
  const pathname = usePathname();
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || !("IntersectionObserver" in window)) return;
    document.documentElement.dataset.motion = "";
    const stops = [...reveals(), ...tiles(), ...buttons(), ...faq()];
    return () => {
      stops.forEach((stop) => stop());
      delete document.documentElement.dataset.motion;
    };
  }, [pathname]);
  return null;
}
