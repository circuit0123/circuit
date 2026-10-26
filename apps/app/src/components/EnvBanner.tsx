"use client";

import Link from "next/link";
import { useEffect, useRef } from "react";
import { SCENARIOS, currentScenario, restartSignup, switchScenario, useAppearance, useFeatures, useMe, usePersonaSignIn, usePersonas, useSession, MOCK, type Scenario, type Theme } from "@/data";
import { APP_ENV, SHOW_DEV_TOOLS } from "@/lib/env";

/** What the banner says, per PRODUCTION.md §2: Dev, Demo, Staging, and Beta in production while BETA_MODE is on. Null means no banner. */
function label(env: string, betaMode: boolean): string | null {
  if (MOCK) return `Mock — ${SCENARIOS.find((s) => s.id === currentScenario())?.label ?? "Default"}`;
  if (env === "dev") return "Dev";
  if (env === "demo") return "Demo — sample data";
  if (env === "staging") return "Staging";
  return betaMode ? "Beta" : null;
}

/**
 * The environment banner, in every environment where it applies. In dev and demo (F9) it also carries the persona switcher, a theme
 * switch and a link to /design; in mock mode, the scenario switcher instead of personas. Never shows tools in staging or production.
 */
export function EnvBanner() {
  const features = useFeatures();
  const text = label(APP_ENV, features.betaMode);
  const ref = useRef<HTMLDivElement>(null);
  // The desktop rail sits below the banner; it reads the banner height from this variable.
  useEffect(() => {
    document.documentElement.style.setProperty("--dev-bar", ref.current ? `${ref.current.offsetHeight}px` : "0px");
  });
  if (!text) return null;
  return (
    <div ref={ref} role="region" aria-label="Environment" className="no-scrollbar relative z-30 flex min-h-8 items-center gap-x-3 overflow-x-auto whitespace-nowrap bg-surface px-4 py-1 t-caption text-text-muted">
      <span className="font-semibold text-text">{text}</span>
      {SHOW_DEV_TOOLS && <Tools />}
    </div>
  );
}

function Tools() {
  const { signOut } = useSession();
  const me = useMe().data;
  const { appearance, save } = useAppearance();
  const personas = usePersonas().data ?? [];
  const switchTo = usePersonaSignIn();
  return (
    <>
      <span className="hidden min-w-0 flex-1 truncate lg:block">{me ? `Signed in as ${me.name}` : "Not signed in"}</span>
      {MOCK ? (
        <label className="flex items-center gap-1">
          Scenario
          <select aria-label="Scenario" value={currentScenario()} onChange={(e) => switchScenario(e.target.value as Scenario)} className="rounded bg-bg px-1 py-0.5 text-text">
            {SCENARIOS.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
      ) : (
        me && personas.length > 0 && (
          <label className="flex items-center gap-1">
            Persona
            <select aria-label="Persona" value="" onChange={(e) => e.target.value && switchTo.mutate(e.target.value)} className="rounded bg-bg px-1 py-0.5 text-text">
              <option value="">Switch to…</option>
              {personas.map((p) => <option key={p.key} value={p.key}>{p.name} · {p.role}</option>)}
            </select>
          </label>
        )
      )}
      <label className="flex items-center gap-1">
        Theme
        <select aria-label="Theme" value={appearance?.theme ?? "system"} onChange={(e) => save.mutate({ theme: e.target.value as Theme })} className="rounded bg-bg px-1 py-0.5 text-text">
          <option value="system">System</option>
          <option value="dark">Dark</option>
          <option value="light">Light</option>
        </select>
      </label>
      <Link href="/design" className="min-h-6 underline">Design</Link>
      {/* Only where it can work: the mock keeps its member in the browser. A real server keeps a finished sign-up. */}
      {MOCK && <button onClick={() => void signOut().then(restartSignup)} className="min-h-6 underline">Replay onboarding</button>}
      <button onClick={() => void signOut()} className="min-h-6 underline">Sign out</button>
    </>
  );
}
