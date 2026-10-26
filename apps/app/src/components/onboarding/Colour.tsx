"use client";

import { AccentPicker, Button, Step } from "@circuit/ui";
import type { Flow } from "@/data";

/** Step 13 (optional). Trying a colour applies it at once, so the bar and the preview show what it will look like. Skip keeps what it was. */
export function Colour({ flow }: { flow: Flow }) {
  return (
    <Step
      title="Pick your colour."
      subhead="It marks what's live and new. Change it any time in Settings."
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      onSkip={flow.saving ? undefined : () => void flow.actions.colour(true)}
      footer={
        <>
          {flow.error && <p role="alert" className="t-footnote text-danger">{flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={flow.saving} onClick={() => void flow.actions.colour(false)}>Continue</Button>
        </>
      }
    >
      <AccentPicker value={flow.accent} onChange={flow.setAccent} className="mt-4" />
    </Step>
  );
}
