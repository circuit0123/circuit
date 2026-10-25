"use client";

import { useSyncExternalStore } from "react";
import type { Role } from "./env";

/**
 * While the app has no /join screen (NEXT_PUBLIC_JOIN_LIVE off), a call to action scrolls to the waitlist form instead. This remembers which role the
 * button stood for, so the form can preselect it, and counts clicks so the form knows to focus its first field.
 */
type Picked = { role: Role | null; clicks: number };

let state: Picked = { role: null, clicks: 0 };
const listeners = new Set<() => void>();

export function chooseRole(role: Role | undefined) {
  state = { role: role ?? state.role, clicks: state.clicks + 1 };
  listeners.forEach((l) => l());
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

export function usePicked(): Picked {
  return useSyncExternalStore(subscribe, () => state, () => state);
}
