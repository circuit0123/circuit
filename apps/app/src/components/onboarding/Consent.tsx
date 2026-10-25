"use client";

import { Button, Step } from "@circuit/ui";
import { problemOf, useConsent } from "@/data";
import { LegalLink } from "../Legal";

/** Shown when the member hasn't accepted the current terms and privacy policy. Comes before the invite screen (B3). */
export function Consent() {
  const consent = useConsent();
  const failed = consent.isError ? (problemOf(consent.error).kind === "network" ? problemOf(consent.error).message : "Couldn't save that. Try again.") : null;
  return (
    <Step
      title="Before you start."
      subhead="Two things to read, in plain words."
      footer={
        <>
          {failed && <p role="alert" className="t-footnote text-danger">{failed}</p>}
          <Button variant="primary" className="w-full" disabled={consent.isPending} onClick={() => consent.mutate()}>I agree</Button>
        </>
      }
    >
      <ul className="flex flex-col gap-4 t-body">
        <li>Read the <LegalLink path="/terms">Terms</LegalLink> and the <LegalLink path="/privacy">Privacy Policy</LegalLink>.</li>
        <li className="text-text-muted">We never sell your data. You can download it or delete your account any time in Settings.</li>
      </ul>
    </Step>
  );
}
