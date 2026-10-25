"use client";

import { Button } from "@circuit/ui/Button";
import { WAITLIST_ROLES } from "@/content/home";
import type { Role } from "@/lib/env";
import { useSrc } from "@/lib/src";
import { fieldClass, MESSAGES, useReady, useWaitlistSubmit } from "@/lib/waitlist";
import { Container } from "./Container";

type Props = {
  /** The page's own label (`landing-home`, `landing-investors` …); a valid `?src=` in the address replaces it. */
  src: string;
  /** Set when the page is for one audience: the role select is left out and this role is sent. */
  role?: Role;
  /** `section` = its own block with a heading (home); `inline` = just the form, for a page that already has a heading (investors). */
  layout?: "section" | "inline";
  heading?: string;
  copy?: React.ReactNode;
};

/**
 * Email, role and city to the public waitlist endpoint. The API answers 202 for an address that is already on the list, so a repeat
 * shows the same message and never reveals who has signed up. Nothing typed here is logged or sent anywhere else.
 * The fields are switched on once the page has loaded; without JavaScript the "Join the beta" button still works.
 */
export function Waitlist({ src, role, layout = "section", heading = "Ask for an invite", copy }: Props) {
  const ready = useReady();
  const label = useSrc(src);
  const { busy, result, submit } = useWaitlistSubmit();

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);
    void submit({
      email: String(data.get("email") ?? "").trim(),
      role: role ?? String(data.get("role") ?? ""),
      city: String(data.get("city") ?? "").trim(),
      src: label,
    });
  }

  const form =
    result === "ok" ? (
      <p role="status" className="t-body">You&rsquo;re on the list. We&rsquo;ll email you when there&rsquo;s a place for you.</p>
    ) : (
      <form onSubmit={onSubmit} aria-describedby="waitlist-msg" className="max-w-[540px]">
        <fieldset disabled={!ready || busy} className="flex flex-col gap-4">
          <legend className="sr-only">Join the waitlist</legend>
          <label className="flex flex-col gap-2 t-subhead text-text-muted">
            Email
            <input name="email" type="email" required autoComplete="email" maxLength={254} placeholder="name@example.com" className={fieldClass} />
          </label>
          {role ? null : (
            <label className="flex flex-col gap-2 t-subhead text-text-muted">
              I am a
              <select name="role" required defaultValue="" className={fieldClass}>
                <option value="" disabled>Choose one</option>
                {WAITLIST_ROLES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>
            </label>
          )}
          <label className="flex flex-col gap-2 t-subhead text-text-muted">
            City
            <input name="city" type="text" autoComplete="address-level2" maxLength={100} className={fieldClass} />
          </label>
          <Button type="submit" variant="secondary" className="w-full">{busy ? "Sending" : "Join the waitlist"}</Button>
        </fieldset>
        <p id="waitlist-msg" role="alert" className="mt-4 t-subhead text-danger empty:hidden">{result ? MESSAGES[result] : null}</p>
        <noscript><p className="mt-4 t-subhead text-text-muted">This form needs JavaScript. Please come back with it switched on.</p></noscript>
      </form>
    );

  if (layout === "inline") return <div id="waitlist" className="scroll-mt-4">{form}</div>;
  return (
    <section id="waitlist" aria-labelledby="waitlist-h" className="scroll-mt-4">
      <Container className="grid gap-8 pb-20 lg:grid-cols-2 lg:gap-16 lg:pb-[120px]">
        <div>
          <h2 id="waitlist-h" className="t-title1">{heading}</h2>
          {copy ? <p className="mt-3 max-w-[540px] t-body text-text-muted">{copy}</p> : null}
        </div>
        {form}
      </Container>
    </section>
  );
}
