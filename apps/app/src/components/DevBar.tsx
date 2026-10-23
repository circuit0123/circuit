"use client";

import { useEffect, useRef } from "react";
import { APP_ENV, SHOW_DEV_TOOLS } from "@/lib/env";
import { useSession } from "./Providers";
import { useMe } from "@/hooks/home";

function setTheme(t: "system" | "dark" | "light") {
  if (t === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  try { if (t === "system") localStorage.removeItem("circuit.theme"); else localStorage.setItem("circuit.theme", t); } catch { /* ignore */ }
}

/** Environment banner + persona and theme switchers. Dev and demo only (F9); never rendered in staging or production. */
export function DevBar() {
  const { signOut } = useSession();
  const me = useMe().data;
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    document.documentElement.style.setProperty("--dev-bar", ref.current ? `${ref.current.offsetHeight}px` : "0px");
  });
  if (!SHOW_DEV_TOOLS) return null;
  return (
    <div ref={ref} role="region" aria-label="Development tools" className="relative z-30 flex min-h-8 flex-wrap items-center gap-x-3 bg-surface-2 px-4 py-1 t-micro text-text-muted">
      <span className="font-semibold text-text">{APP_ENV}</span>
      <span className="min-w-0 flex-1 truncate">{me ? `Signed in as ${me.display_name}` : "Not signed in"}</span>
      <label className="flex items-center gap-1">
        Theme
        <select aria-label="Theme" defaultValue="system" onChange={(e) => setTheme(e.target.value as "system")} className="rounded bg-surface px-1 py-0.5 text-text">
          <option value="system">System</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>
      <button onClick={signOut} className="min-h-6 underline">Switch persona</button>
    </div>
  );
}
