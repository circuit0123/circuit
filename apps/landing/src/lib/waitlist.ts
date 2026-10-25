"use client";

import { useState, useSyncExternalStore } from "react";
import { API_URL } from "./env";

export type Result = "ok" | "invalid" | "limited" | "down";

export const MESSAGES: Record<Exclude<Result, "ok">, string> = {
  invalid: "Check your email address and try again.",
  limited: "Too many tries from this connection. Try again in an hour.",
  down: "Couldn’t reach Circuit. Check your connection and try again.",
};

/** What the public waitlist endpoint accepts (backend/apps/beta/api.py). */
export type WaitlistBody = { email: string; role: string; city: string; college?: string; note?: string; src: string };

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** One call with an 8 second timeout. Network errors and 5xx are retried once after a second; anything else is final. */
export async function send(body: WaitlistBody, retry = true): Promise<Result> {
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), 8000);
  try {
    const res = await fetch(`${API_URL}/api/waitlist`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(body),
      signal: ctl.signal,
    });
    if (res.status === 202) return "ok";
    if (res.status === 429) return "limited";
    if (res.status < 500) return "invalid";
  } catch {
    // network error or timeout: fall through to the retry
  } finally {
    clearTimeout(timer);
  }
  if (!retry) return "down";
  await wait(1000);
  return send(body, false);
}

const noSubscribe = () => () => {};

/** false while the server HTML is shown (and during hydration), true once the page runs in the browser: forms stay switched off until then. */
export function useReady(): boolean {
  return useSyncExternalStore(noSubscribe, () => true, () => false);
}

/** Busy flag + last result for a waitlist form. The API answers 202 for an address already on the list, so a repeat looks like a new sign-up. */
export function useWaitlistSubmit() {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  async function submit(body: WaitlistBody) {
    setBusy(true);
    setResult(null);
    const r = await send(body);
    setBusy(false);
    setResult(r);
  }
  return { busy, result, submit };
}

/** Shared look of the form fields (surface-2 fill, 50px, 12px radius). */
export const fieldClass =
  "min-h-[50px] w-full rounded-control bg-surface-2 px-4 t-body text-text outline-none placeholder:text-text-subtle";
