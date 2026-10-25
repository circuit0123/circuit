"use client";

import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { useKey } from "./keys";

export type Capability = { slug: string; name: string; category: string };

/** The fixed list of 40–80 capabilities that offers, needs and skills are picked from. Changes rarely, so it is kept for the session. */
export function useCapabilities() {
  const { key, enabled } = useKey("capabilities");
  return useQuery({
    queryKey: key,
    enabled,
    staleTime: Infinity,
    queryFn: async (): Promise<Capability[]> => (await unwrap(api.GET("/api/capabilities"))).map((c) => ({ slug: c.slug, name: c.name, category: c.category })),
  });
}
