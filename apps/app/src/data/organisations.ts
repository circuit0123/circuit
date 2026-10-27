"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, unwrap } from "./client";
import { useKey } from "./keys";

/**
 * Colleges and programmes matching what was typed (sign-up step 11): up to 10 names from `GET /api/organisations/search`, asked
 * 250 ms after the last key. Picking one only fills in the college name; the screen offers what was typed when nothing matches.
 */
export function useOrganisationSearch(query: string): string[] {
  const [q, setQ] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ(query.trim()), 250);
    return () => clearTimeout(t);
  }, [query]);
  const { key, enabled } = useKey("organisation-search", q);
  const found = useQuery({
    queryKey: key,
    enabled: enabled && q.length >= 2,
    queryFn: async () => (await unwrap(api.GET("/api/organisations/search", { params: { query: { q } } }))).map((o) => o.name),
  });
  return q.length >= 2 && query.trim() === q ? found.data ?? [] : [];
}
