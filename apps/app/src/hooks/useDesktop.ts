"use client";

import { useEffect, useState } from "react";

/** True at ≥1024px (DESIGN.md §3). Lets Home render the Daily Drop in one place only. */
export function useDesktop(): boolean {
  const [on, setOn] = useState(false);
  useEffect(() => {
    const m = window.matchMedia("(min-width: 1024px)");
    const f = () => setOn(m.matches);
    f();
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, []);
  return on;
}
