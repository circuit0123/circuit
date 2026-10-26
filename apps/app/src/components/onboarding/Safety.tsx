"use client";

import { Button, Step } from "@circuit/ui";
import type { Flow } from "@/data";

/** Shown only to members under 18, before Where (DESIGN.md §4 "Consent"). Plain words about the defaults we switch on. */
export function Safety({ flow }: { flow: Flow }) {
  return (
    <Step
      title="We've made a few things private."
      subhead="Because you're under 18, these are on from the start."
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      footer={
        <>
          {flow.error && <p role="alert" className="t-footnote text-danger">{flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={flow.saving} onClick={() => void flow.actions.safety()}>Got it</Button>
        </>
      }
    >
      <ul className="flex flex-col gap-4 t-body">
        <li>Your profile is hidden from people outside Circuit's members.</li>
        <li>People you haven't connected with can't send you requests.</li>
      </ul>
    </Step>
  );
}
