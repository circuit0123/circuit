"use client";

import { MOCK } from "./mocks/config";
import { ORGANISATIONS } from "./missing";

/**
 * Colleges and programmes matching what was typed (sign-up step 11). API needed: there is no organisation search yet, so real builds
 * return nothing and the screen offers what the person typed; mock mode searches a marked stand-in list.
 */
export function useOrganisationSearch(query: string): string[] {
  const q = query.trim().toLowerCase();
  if (!MOCK || q.length < 2) return [];
  return ORGANISATIONS.filter((o) => o.toLowerCase().includes(q)).slice(0, 6);
}
