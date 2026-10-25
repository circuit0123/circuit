"use client";

import { useState, useSyncExternalStore } from "react";
import { Button } from "@circuit/ui/Button";
import { SRC, WAITLIST_ROLES } from "@/content/home";
import { API_URL } from "@/lib/env";
import { Container } from "./Container";

type Result = "ok" | "invalid" | "limited" | "down";

const MESSAGES: Record<Exclude<Result, "ok">, string> = {
  invalid: "Check your email address and try again.",
  limited: "Too many tries from this connection. Try again in an hour.",
  down: "Couldn’t reach Circuit. Check your connection and try again.",
};

const noSubscribe = () => () => {};
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

/** One call with an 8 second timeout. Network errors and 5xx are retried once after a second; anything else is final. */
async function send(body: Record<string, string>, retry = true): Promise<Result> {
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

const field = "min-h-[50px] w-full rounded-control bg-surface-2 px-4 t-body text-text outline-none placeholder:text-text-subtle";

/**
 * Email, role and city to the public waitlist endpoint. The API answers 202 for an address that is already on the list, so a repeat
 * shows the same message and never reveals who has signed up. Nothing typed here is logged or sent anywhere else.
 * The fields are switched on once the page has loaded; without JavaScript the "Join the beta" button above still works.
 */
export function Waitlist() {
  // false while the server HTML is shown (and during hydration), true once the page is running in the browser.
  const ready = useSyncExternalStore(noSubscribe, () => true, () => false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<Result | null>(null);

  async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    setBusy(true);
    setResult(null);
    const r = await send({
      email: String(data.get("email") ?? "").trim(),
      role: String(data.get("role") ?? ""),
      city: String(data.get("city") ?? "").trim(),
      src: SRC,
    });
    setBusy(false);
    setResult(r);
  }

  return (
    <section id="waitlist" aria-labelledby="waitlist-h" className="scroll-mt-4">
      <Container className="grid gap-8 pb-20 lg:grid-cols-2 lg:gap-16 lg:pb-[120px]">
        <div>
          <h2 id="waitlist-h" className="t-title1">Ask for an invite</h2>
          <p className="mt-3 max-w-[540px] t-body text-text-muted">
            We are opening Circuit one city and one college at a time. Leave your email and we&rsquo;ll write when there&rsquo;s a place for you.
          </p>
        </div>
        {result === "ok" ? (
          <p role="status" className="t-body">You&rsquo;re on the list. We&rsquo;ll email you when there&rsquo;s a place for you.</p>
        ) : (
          <form onSubmit={onSubmit} aria-describedby="waitlist-msg" className="max-w-[540px]">
            <fieldset disabled={!ready || busy} className="flex flex-col gap-4">
              <legend className="sr-only">Join the waitlist</legend>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                Email
                <input name="email" type="email" required autoComplete="email" maxLength={254} placeholder="name@example.com" className={field} />
              </label>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                I am a
                <select name="role" required defaultValue="" className={field}>
                  <option value="" disabled>Choose one</option>
                  {WAITLIST_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
                </select>
              </label>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                City
                <input name="city" type="text" autoComplete="address-level2" maxLength={100} className={field} />
              </label>
              <Button type="submit" variant="secondary" className="w-full">{busy ? "Sending" : "Join the waitlist"}</Button>
            </fieldset>
            <p id="waitlist-msg" role="alert" className="mt-4 t-subhead text-danger empty:hidden">{result ? MESSAGES[result] : null}</p>
            <noscript><p className="mt-4 t-subhead text-text-muted">This form needs JavaScript. You can still use &ldquo;Join the beta&rdquo; at the top of the page.</p></noscript>
          </form>
        )}
      </Container>
    </section>
  );
}
