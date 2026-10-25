"use client";

import { useEffect, useLayoutEffect, useRef } from "react";

/** Theme and accent (DESIGN.md §5). The words here are the design's; the API's names are mapped in the app's data layer. */
export type Theme = "system" | "dark" | "light";
export type Accent = "emerald" | "sky" | "indigo" | "rose" | "lime" | "mono";
export type Appearance = { theme: Theme; accent: Accent; swipeTabs: boolean };

/** The six accents with their `current` colour in each theme. Only these; there is no free colour picker. */
export const ACCENTS: ReadonlyArray<{ id: Accent; label: string; dark: string; light: string }> = [
  { id: "emerald", label: "Emerald", dark: "#2FBF8A", light: "#00563F" },
  { id: "sky", label: "Sky", dark: "#5AC8FA", light: "#004E8C" },
  { id: "indigo", label: "Indigo", dark: "#8E8CFF", light: "#3B2F9E" },
  { id: "rose", label: "Rose", dark: "#FF6482", light: "#8A1238" },
  { id: "lime", label: "Lime", dark: "#B6E85A", light: "#285004" },
  { id: "mono", label: "Mono", dark: "#F3EEF5", light: "#120309" },
];

/** The browser chrome colour: true black in dark, the `bg` lavender in light. */
export const THEME_COLOR = { dark: "#000000", light: "#C2BCC8" } as const;

/** Where the last known appearance is kept so the next load can paint it before any script of the app runs. */
export const APPEARANCE_CACHE_KEY = "circuit.appearance";

/**
 * Inline this in <head>. It runs before first paint: puts the cached theme and accent on <html> and adds the
 * theme-color tag, so there is no flash of the default colour. Keep it in step with `applyAppearance`.
 */
export const firstPaintScript = `try{var d=document.documentElement,a=JSON.parse(localStorage.getItem("${APPEARANCE_CACHE_KEY}")||"{}");if(a.theme==="dark"||a.theme==="light")d.dataset.theme=a.theme;if(/^(sky|indigo|rose|lime|mono)$/.test(a.accent))d.dataset.accent=a.accent;var t=a.theme==="dark"||a.theme==="light"?a.theme:(matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"),m=document.createElement("meta");m.name="theme-color";m.setAttribute("data-circuit","");m.content=t==="light"?"${THEME_COLOR.light}":"${THEME_COLOR.dark}";document.head.prepend(m)}catch(e){}`;

const prefersLight = () => window.matchMedia("(prefers-color-scheme: light)").matches;

function setThemeColor(theme: Theme) {
  const resolved = theme === "system" ? (prefersLight() ? "light" : "dark") : theme;
  let m = document.head.querySelector<HTMLMetaElement>('meta[name="theme-color"][data-circuit]');
  if (!m) {
    m = document.createElement("meta");
    m.name = "theme-color";
    m.setAttribute("data-circuit", "");
    document.head.prepend(m);
  }
  m.content = THEME_COLOR[resolved];
}

/** Puts theme and accent on <html> and the chrome colour on the theme-color tag. */
export function applyAppearance({ theme, accent }: Pick<Appearance, "theme" | "accent">) {
  const d = document.documentElement;
  if (theme === "system") delete d.dataset.theme;
  else d.dataset.theme = theme;
  if (accent === "emerald") delete d.dataset.accent;
  else d.dataset.accent = accent;
  setThemeColor(theme);
}

const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

/**
 * Applies the member's appearance (props are undefined until it is known). A theme change after the first paint crossfades through a view transition (instant when the
 * browser has none, or for reduced motion); an accent change crossfades in CSS (`transition: --current` in tokens.css).
 */
export function ThemeProvider({ theme, accent, children }: { theme?: Theme; accent?: Accent; children: React.ReactNode }) {
  const first = useRef(true);
  const last = useRef<Theme | null>(null);

  useIsoLayoutEffect(() => {
    // Until the member's saved appearance is known, whatever the first-paint script put on <html> stays.
    if (!theme || !accent) return;
    const change = () => applyAppearance({ theme, accent });
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = (document as Document & { startViewTransition?: (cb: () => void) => unknown }).startViewTransition?.bind(document);
    if (!first.current && last.current !== theme && start && !reduce) start(change);
    else change();
    first.current = false;
    last.current = theme;
    try { localStorage.setItem(APPEARANCE_CACHE_KEY, JSON.stringify({ theme, accent })); } catch { /* private mode: not cached */ }
  }, [theme, accent]);

  // "System" follows the phone's light/dark switch, including the chrome colour.
  useEffect(() => {
    if (theme !== "system") return;
    const m = window.matchMedia("(prefers-color-scheme: light)");
    const f = () => setThemeColor("system");
    m.addEventListener("change", f);
    return () => m.removeEventListener("change", f);
  }, [theme]);

  return <>{children}</>;
}
