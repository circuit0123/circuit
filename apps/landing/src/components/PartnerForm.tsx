"use client";

import { useEffect, useRef } from "react";
import { Button } from "@circuit/ui/Button";
import { usePicked } from "@/lib/join";
import { useSrc } from "@/lib/src";
import { fieldClass, MESSAGES, useReady, useWaitlistSubmit } from "@/lib/waitlist";
import { Container } from "./Container";

const SRC = "landing-partners";

/**
 * Shown on /partners while `partner_mode` is off (no partner role in the app yet). Name, organisation, city, email and a note go to the
 * public waitlist endpoint with role=partner: nothing else is called. The endpoint has no name or organisation field, so the
 * organisation goes in `college` and the name is the first line of `note`.
 */
export function PartnerForm({ intro }: { intro?: string }) {
  const ready = useReady();
  const src = useSrc(SRC);
  const { busy, result, submit } = useWaitlistSubmit();
  const picked = usePicked();
  const name = useRef<HTMLInputElement>(null);
  const seenClicks = useRef(picked.clicks);
  useEffect(() => {
    // The button above was pressed: the page has scrolled here, so put the cursor in the first field.
    if (picked.clicks !== seenClicks.current) {
      seenClicks.current = picked.clicks;
      name.current?.focus({ preventScroll: true });
    }
  }, [picked.clicks]);

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const d = new FormData(e.currentTarget);
    const text = (k: string) => String(d.get(k) ?? "").trim();
    const note = text("note");
    void submit({
      email: text("email"),
      role: "partner",
      city: text("city"),
      college: text("organisation"),
      note: `Name: ${text("name")}${note ? `\n${note}` : ""}`,
      src,
    });
  }

  return (
    <section id="partner-form" aria-labelledby="partner-form-h" className="scroll-mt-4">
      <Container className="grid gap-8 pb-20 lg:grid-cols-2 lg:gap-16 lg:pb-[120px]">
        <div>
          <h2 id="partner-form-h" className="t-title1">Bring Circuit to your campus</h2>
          <p className="mt-3 max-w-[540px] t-body text-text-muted">
            {intro ? `${intro} ` : ""}Tell us about your organisation. We&rsquo;ll write to you to arrange a short call and to check the organisation before anyone gets admin powers.
          </p>
        </div>
        {result === "ok" ? (
          <p role="status" className="t-body">Thanks. We&rsquo;ll write to you soon.</p>
        ) : (
          <form onSubmit={onSubmit} aria-describedby="partner-msg" className="max-w-[540px]">
            <fieldset disabled={!ready || busy} className="flex flex-col gap-4">
              <legend className="sr-only">Contact us about your organisation</legend>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                Your name
                <input ref={name} name="name" type="text" required autoComplete="name" maxLength={80} className={fieldClass} />
              </label>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                Organisation
                <input name="organisation" type="text" required autoComplete="organization" maxLength={200} className={fieldClass} />
              </label>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                City
                <input name="city" type="text" required autoComplete="address-level2" maxLength={100} className={fieldClass} />
              </label>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                Email
                <input name="email" type="email" required autoComplete="email" maxLength={254} placeholder="name@example.com" className={fieldClass} />
              </label>
              <label className="flex flex-col gap-2 t-subhead text-text-muted">
                Note (optional)
                <textarea name="note" rows={3} maxLength={400} className={`${fieldClass} min-h-[96px] py-3`} />
              </label>
              <Button type="submit" variant="secondary" className="w-full">{busy ? "Sending" : "Send to Circuit"}</Button>
            </fieldset>
            <p id="partner-msg" role="alert" className="mt-4 t-subhead text-danger empty:hidden">{result ? MESSAGES[result] : null}</p>
            <noscript><p className="mt-4 t-subhead text-text-muted">This form needs JavaScript. Please come back with it switched on.</p></noscript>
          </form>
        )}
      </Container>
    </section>
  );
}
