"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { useMe, useSaveAppearance, useSession, type Theme } from "@/data";
import { APP_ENV, SHOW_DEV_TOOLS } from "@/lib/env";

/** Environment banner + persona and theme switchers. Dev and demo only (F9); never rendered in staging or production. */
export function DevBar() {
  const { signOut } = useSession();
  const me = useMe().data;
  const save = useSaveAppearance();
  const ref = useRef<HTMLDivElement>(null);
  // The desktop rail sits below the banner; it reads the banner height from this variable.
  useEffect(() => {
    document.documentElement.style.setProperty("--dev-bar", ref.current ? `${ref.current.offsetHeight}px` : "0px");
  });
  if (!SHOW_DEV_TOOLS) return null;
  return (
    <div ref={ref} role="region" aria-label="Development tools" className="relative z-30 flex min-h-8 flex-wrap items-center gap-x-3 bg-surface-2 px-4 py-1 t-caption text-text-muted">
      <span className="font-semibold text-text">{APP_ENV}</span>
      <span className="min-w-0 flex-1 truncate">{me ? `Signed in as ${me.name}` : "Not signed in"}</span>
      <label className="flex items-center gap-1">
        Theme
        <select aria-label="Theme" value={me?.appearance.theme ?? "system"} onChange={(e) => save.mutate({ theme: e.target.value as Theme })} className="rounded bg-surface px-1 py-0.5 text-text">
          <option value="system">System</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>
      <Link href="/onboarding" className="min-h-6 underline">Replay onboarding</Link>
      <button onClick={() => void signOut()} className="min-h-6 underline">Switch persona</button>
    </div>
  );
}
