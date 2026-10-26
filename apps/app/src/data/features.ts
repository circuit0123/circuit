"use client";

import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { useKey } from "./keys";

export type FeatureName = "pulse" | "daily_drop" | "circuits" | "investor_mode" | "partner_mode" | "promotions" | "payments";

/**
 * Features this build has screens for. A flag can be on at the server for a feature the app
 * doesn't draw yet (circuits, investor and partner mode, promotions, payments); those stay hidden
 * here so nobody lands on a missing screen. Add a name when its screens ship.
 */
const BUILT: ReadonlySet<FeatureName> = new Set(["pulse", "daily_drop"]);

/** GET /api/config (public, cached 60s). The one place the app asks "is this feature on for me?" (DESIGN.md §3). */
export function useFeatures() {
  const { token } = useKey();
  const key = [token ? "in" : "out", "config"];
  const q = useQuery({
    queryKey: key,
    staleTime: 60_000,
    queryFn: async () => {
      const c = await unwrap(api.GET("/api/config"));
      return { env: c.env, betaMode: c.beta_mode, betaAccess: c.beta_access, flags: c.features as Record<string, boolean> };
    },
  });
  const flags = q.data?.flags;
  return {
    ready: q.isSuccess,
    isError: q.isError,
    env: q.data?.env,
    betaMode: q.data?.betaMode ?? false,
    betaAccess: q.data?.betaAccess ?? true,
    /** True only when the server flag is on for this member and the app has the screens. */
    on: (name: FeatureName) => !!flags?.[name] && BUILT.has(name),
    /** The server flag alone, whether or not this build has the screens. Only for items that arrive inside a feed already built (partner and promoted slots in Pulse). */
    raw: (name: FeatureName) => !!flags?.[name],
  };
}
