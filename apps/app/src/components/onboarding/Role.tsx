"use client";

import { Step } from "@circuit/ui";
import type { Flow } from "@/data";
import { ChoiceRow } from "./ChoiceRow";

/** Step 5. Choosing a row advances at once. A row whose feature is off isn't listed. */
export function Role({ flow }: { flow: Flow }) {
  return (
    <Step title="What brings you here?" subhead="You can add more later." progress={flow.progress} onBack={flow.canGoBack ? flow.back : undefined}>
      <div className="flex flex-col gap-3">
        {flow.roles.map((r) => (
          <ChoiceRow key={r.choice} label={r.label} disabled={flow.saving} onClick={() => void flow.actions.role(r.choice)} />
        ))}
      </div>
      {flow.error && <p role="alert" className="t-footnote mt-4 text-danger">{flow.error}</p>}
    </Step>
  );
}
