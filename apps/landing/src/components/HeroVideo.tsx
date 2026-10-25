"use client";

import { useEffect, useRef, useState } from "react";

const SIZE = 540;

/**
 * The brand video as a small, muted, looping square. The poster (the video's last frame) is plain HTML, so the page is complete
 * before anything plays and stays complete without JavaScript. The video is only added after the page has loaded, when the
 * square is on screen, and never when the person asked for less motion or saves data (then the poster simply stays).
 */
export function HeroVideo() {
  const box = useRef<HTMLDivElement>(null);
  const [play, setPlay] = useState(false);
  const [shown, setShown] = useState(false);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
    let io: IntersectionObserver | undefined;
    let cancelled = false;

    const start = () => {
      if (cancelled || reduce.matches || saveData || !box.current) return;
      io = new IntersectionObserver(([e]) => {
        if (e?.isIntersecting) { setPlay(true); io?.disconnect(); }
      });
      io.observe(box.current);
    };
    // The headline stagger (DESIGN.md §7) takes up to 700ms; the video starts after it.
    const whenIdle = () => {
      const ric = (window as Window & { requestIdleCallback?: (cb: () => void) => number }).requestIdleCallback;
      setTimeout(() => (ric ? ric(start) : start()), Math.max(200, 700 - performance.now()));
    };
    if (document.readyState === "complete") whenIdle();
    else window.addEventListener("load", whenIdle, { once: true });

    const onChange = () => { if (reduce.matches) { setPlay(false); setShown(false); } };
    reduce.addEventListener("change", onChange);
    return () => {
      cancelled = true;
      io?.disconnect();
      window.removeEventListener("load", whenIdle);
      reduce.removeEventListener("change", onChange);
    };
  }, []);

  return (
    <div ref={box} aria-hidden="true" className="relative aspect-square w-full max-w-[320px] overflow-hidden rounded-sheet lg:w-[360px] lg:max-w-none">
      {/* eslint-disable-next-line @next/next/no-img-element -- static export, one fixed-size image */}
      <img src="/brand/circuit-logo-poster.webp" width={SIZE} height={SIZE} alt="" fetchPriority="high" className="absolute inset-0 h-full w-full" />
      {play ? (
        <video
          muted
          loop
          autoPlay
          playsInline
          preload="none"
          tabIndex={-1}
          poster="/brand/circuit-logo-poster.webp"
          onPlaying={() => setShown(true)}
          className={`absolute inset-0 h-full w-full transition-opacity duration-150 ${shown ? "opacity-100" : "opacity-0"}`}
        >
          <source src="/brand/circuit-logo.mp4" type="video/mp4" />
        </video>
      ) : null}
    </div>
  );
}
