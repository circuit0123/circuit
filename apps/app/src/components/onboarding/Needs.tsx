"use client";

import { LIMITS, type Flow } from "@/data";
import { ChipPicker } from "./ChipPicker";

/** Step 10. What the person needs right now: the same picker as Offers, up to three. */
export function Needs({ flow }: { flow: Flow }) {
  const saved = flow.answers.needs?.slugs as string[] | undefined;
  const suggested = flow.suggestions.needs;
  return (
    <ChipPicker
      flow={flow}
      title="And what you need right now."
      subhead={suggested.length ? "These came from what you wrote. Change them if they're off." : `Pick up to ${LIMITS.needs} things you'd like help with.`}
      limit={LIMITS.needs}
      suggested={suggested}
      initial={saved ?? suggested.slice(0, LIMITS.needs)}
      noun="need"
      onSave={flow.actions.needs}
    />
  );
}
