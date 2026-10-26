"use client";

import { Step } from "@circuit/ui";
import type { Flow } from "@/data";
import { ChoiceRow } from "./ChoiceRow";

/** Step 6. Two equal rows, neither is "the" button. "Not yet" leads to the safety screen. */
export function Age({ flow }: { flow: Flow }) {
  return (
    <Step title="Are you 18 or older?" progress={flow.progress} onBack={flow.canGoBack ? flow.back : undefined}>
      <div className="flex flex-col gap-3">
        <ChoiceRow label="Yes" chevron={false} disabled={flow.saving} onClick={() => void flow.actions.age(true)} />
        <ChoiceRow label="Not yet" chevron={false} disabled={flow.saving} onClick={() => void flow.actions.age(false)} />
      </div>
      <p className="t-footnote mt-4 text-text-muted">We ask so we can keep younger members safer by default.</p>
      {flow.error && <p role="alert" className="t-footnote mt-3 text-danger">{flow.error}</p>}
    </Step>
  );
}
