"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { animate } from "motion/mini";
import { hover, inView, press, spring } from "motion";

/**
 * Landing site motion (DESIGN.md §7), switched on once the page has loaded. Renders nothing.
 * The server HTML is complete and readable; this only adds movement on top. Rules: transform, opacity and stroke-dashoffset only,
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

/**
 * The Bridge arch: a thin `current` line drawn once between the three "How it works" steps (1 → 2, then 2 → 3, 450ms each).
 * It is built here, so it exists only when motion does. With the steps in a row it arches over the empty part of the number row;
 * stacked on a phone it bows through the page's left gutter. Absolutely positioned, so it never affects the layout.
 */
function bridge(): Stop[] {
  const wrap = document.querySelector<HTMLElement>("[data-bridge]");
  const numbers = wrap ? Array.from(wrap.querySelectorAll<HTMLElement>("[data-step-n]")) : [];
  if (!wrap || numbers.length < 3) return [];

  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("aria-hidden", "true");
  svg.style.cssText = "position:absolute;inset:0;width:100%;height:100%;overflow:visible;pointer-events:none";
  const paths = [0, 1].map(() => {
    const p = document.createElementNS(NS, "path");
    p.setAttribute("fill", "none");
    p.setAttribute("stroke-width", "1.5");
    p.setAttribute("pathLength", "1");
    p.style.cssText = "stroke:var(--current);stroke-dasharray:1;stroke-dashoffset:1";
    svg.append(p);
    return p;
  });
  wrap.append(svg);

  const place = () => {
    const base = wrap.getBoundingClientRect();
    const at = numbers.map((n) => {
      const range = document.createRange();
      range.selectNodeContents(n);
      const b = range.getBoundingClientRect();
      // The middle of the digits, not of the text box (which has room for descenders): about 0.57em above the box bottom.
      return { x: b.left - base.left, y: b.bottom - base.top - 0.57 * parseFloat(getComputedStyle(n).fontSize), w: b.width };
    });
    const inARow = Math.abs(at[0].y - at[1].y) < 4;
    paths.forEach((p, i) => {
      const a = at[i];
      const b = at[i + 1];
      if (inARow) {
        const x1 = a.x + a.w + 12;
        const x2 = b.x - 12;
        p.setAttribute("d", `M${x1} ${a.y} Q${(x1 + x2) / 2} ${a.y - 28} ${x2} ${b.y}`);
      } else {
        p.setAttribute("d", `M-3 ${a.y + 12} C-14 ${a.y + 90} -14 ${b.y - 90} -3 ${b.y - 12}`);
      }
    });
  };
  place();
  const resize = new ResizeObserver(place);
  resize.observe(wrap);
  void document.fonts?.ready.then(place);

  // The second line waits for the first, so it reads as one line going 1 → 2 → 3, however the steps come into view.
  let drawn: PromiseLike<unknown> = Promise.resolve();
  const draw = (p: SVGPathElement) => {
    drawn = drawn.then(() => animate(p, { strokeDashoffset: [1, 0] }, { duration: 0.45, ease: [0.4, 0, 0.2, 1] })).then(() => {
      p.style.strokeDashoffset = "0";
    });
  };
  const stops = [1, 2].map((n) => {
    const stop = inView(numbers[n], () => {
      stop();
      draw(paths[n - 1]);
    }, { margin: "0px 0px -15% 0px" });
    return stop;
  });
  return [...stops, () => { resize.disconnect(); svg.remove(); }];
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
    const stops = [...reveals(), ...bridge(), ...tiles(), ...buttons(), ...faq()];
    return () => {
      stops.forEach((stop) => stop());
      delete document.documentElement.dataset.motion;
    };
  }, [pathname]);
  return null;
}
