"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { Accent, Appearance, Theme } from "@circuit/ui";
import { api, unwrap } from "./client";
import { useKey } from "./keys";
import { useMe } from "./me";

export type { Accent, Appearance, Theme };

/**
 * The API calls the default accent "mint"; the design (DESIGN.md §5) calls it Emerald. Screens only ever see "emerald"; the
 * rename on the server side is listed in PROGRESS.md under "Frontend → API needed".
 */
type ApiAccent = "mint" | "sky" | "indigo" | "rose" | "lime" | "mono";
export const accentFromApi = (a: ApiAccent): Accent => (a === "mint" ? "emerald" : a);
export const accentToApi = (a: Accent): ApiAccent => (a === "emerald" ? "mint" : a);

/**
 * The member's theme, accent and swipe toggle, and the way to change them. `appearance` is undefined until it is known (signed out,
 * or still loading); the ThemeProvider then leaves the first-paint colours alone. `save` applies at once (the provider crossfades),
 * saves in the background and puts the old value back if saving fails.
 */
export function useAppearance() {
  const appearance = useMe().data?.appearance;
  const qc = useQueryClient();
  const { key } = useKey("me");
  const save = useMutation({
    mutationFn: (patch: Partial<Appearance>) =>
      unwrap(api.PATCH("/api/me/appearance", { body: { theme: patch.theme, accent: patch.accent ? accentToApi(patch.accent) : undefined, swipe_tabs: patch.swipeTabs } })),
    onMutate: async (patch) => {
      const before = qc.getQueryData<{ appearance: Appearance }>(key);
      if (before) qc.setQueryData(key, { ...before, appearance: { ...before.appearance, ...patch } });
      return { before };
    },
    onError: (_e, _p, ctx) => { if (ctx?.before) qc.setQueryData(key, ctx.before); },
    onSettled: () => qc.invalidateQueries({ queryKey: key }),
  });
  return { appearance, save };
}
