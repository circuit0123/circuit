"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { api, unwrap } from "./client";
import { useKey } from "./keys";
import { useMe } from "./me";

export type Theme = "system" | "dark" | "light";
export type Accent = "mint" | "sky" | "indigo" | "rose" | "lime" | "mono";
export type Appearance = { theme: Theme; accent: Accent; swipeTabs: boolean };

export const ACCENTS: ReadonlyArray<{ id: Accent; label: string; dark: string; light: string }> = [
  { id: "mint", label: "Mint", dark: "#3DDBB0", light: "#0A8A69" },
  { id: "sky", label: "Sky", dark: "#5AC8FA", light: "#0071C2" },
  { id: "indigo", label: "Indigo", dark: "#8E8CFF", light: "#5856D6" },
  { id: "rose", label: "Rose", dark: "#FF6482", light: "#C7254E" },
  { id: "lime", label: "Lime", dark: "#B6E85A", light: "#4D7C0F" },
  { id: "mono", label: "Mono", dark: "#F5F5F7", light: "#1D1D1F" },
];

const CACHE = "circuit.appearance";

/** Sets the theme and accent on <html>. Also called by the inline script in layout.tsx before first paint. */
export function applyAppearance(a: Pick<Appearance, "theme" | "accent">) {
  const d = document.documentElement;
  if (a.theme === "system") delete d.dataset.theme; else d.dataset.theme = a.theme;
  if (a.accent === "mint") delete d.dataset.accent; else d.dataset.accent = a.accent;
}

/** Keeps <html> and the first-paint cache in step with the member's saved appearance. Mounted once in Providers. */
export function useApplyAppearance() {
  const a = useMe().data?.appearance;
  useEffect(() => {
    if (!a) return;
    applyAppearance(a);
    try { localStorage.setItem(CACHE, JSON.stringify({ theme: a.theme, accent: a.accent })); } catch { /* not cached */ }
  }, [a]);
}

/** Change theme, accent or the swipe toggle. Applies at once (crossfade), saves in the background, undoes itself if saving fails. */
export function useSaveAppearance() {
  const qc = useQueryClient();
  const { key } = useKey("me");
  return useMutation({
    mutationFn: (patch: Partial<Appearance>) =>
      unwrap(api.PATCH("/api/me/appearance", { body: { theme: patch.theme, accent: patch.accent, swipe_tabs: patch.swipeTabs } })),
    onMutate: async (patch) => {
      const before = qc.getQueryData<{ appearance: Appearance }>(key);
      if (before) qc.setQueryData(key, { ...before, appearance: { ...before.appearance, ...patch } });
      return { before };
    },
    onError: (_e, _p, ctx) => { if (ctx?.before) qc.setQueryData(key, ctx.before); },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
}
