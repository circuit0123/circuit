"use client";

import { useCallback, useSyncExternalStore } from "react";
import { api } from "./client";

/** What a landing or invite link told us (`/join?role=student&src=landing-students&code=…`). Kept across the sign-in redirect. */
export type JoinContext = { role?: string; src?: string; code?: string; org?: string };
const KEY = "circuit.join";
// No "partner": partner sign-up (and its dashboard) is not in this build, so a `role=partner` link is treated as no role and the person sees the normal Role question, which has no partner row.
const ROLES = ["student", "founder", "mentor", "investor"];
const SRC = /^[a-z0-9_-]{1,40}$/;
const EMPTY: JoinContext = {};

let cache: { raw: string | null; value: JoinContext } = { raw: null, value: EMPTY };
const listeners = new Set<() => void>();

function read(): JoinContext {
  let raw: string | null = null;
  try { raw = localStorage.getItem(KEY); } catch { /* no storage */ }
  if (raw === cache.raw) return cache.value;
  let value = EMPTY;
  try { value = raw ? (JSON.parse(raw) as JoinContext) : EMPTY; } catch { /* ignore a bad value */ }
  cache = { raw, value };
  return value;
}

function write(v: JoinContext | null) {
  try { if (v) localStorage.setItem(KEY, JSON.stringify(v)); else localStorage.removeItem(KEY); } catch { /* ignore */ }
  listeners.forEach((l) => l());
}

/** Cleans values from the URL: unknown roles and odd `src` values are dropped. */
export function parseJoin(params: URLSearchParams): JoinContext {
  const role = params.get("role") ?? undefined;
  const src = params.get("src") ?? undefined;
  const code = params.get("code")?.trim().slice(0, 40) || undefined;
  const org = params.get("org") ?? undefined;
  return {
    role: role && ROLES.includes(role) ? role : undefined,
    src: src && SRC.test(src) ? src : undefined,
    code,
    org: org && /^\d{1,9}$/.test(org) ? org : undefined,
  };
}

export function useJoinContext() {
  const ctx = useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb); }, read, () => EMPTY);
  const save = useCallback((v: JoinContext) => write({ ...read(), ...Object.fromEntries(Object.entries(v).filter(([, x]) => x)) }), []);
  const clear = useCallback(() => write(null), []);
  /** Forget single answers once they are used (an invite code that has been redeemed must not be tried again). */
  const forget = useCallback((...keys: Array<keyof JoinContext>) => {
    const next = { ...read() };
    for (const k of keys) delete next[k];
    write(Object.keys(next).length ? next : null);
  }, []);
  return { ...ctx, save, clear, forget };
}

/**
 * Counts a click on a landing or invite link for the per-source funnel (`POST /api/join/visit`): once per browser session, fire and
 * forget. Stores only a per-day count on the server, never who clicked.
 */
export function reportJoinVisit(src: string | undefined) {
  if (!src) return;
  try {
    if (sessionStorage.getItem("circuit.visit") === src) return;
    sessionStorage.setItem("circuit.visit", src);
  } catch { /* no storage: count it anyway */ }
  void Promise.resolve(api.POST("/api/join/visit", { body: { src } })).catch(() => {});
}
