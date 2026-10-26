"use client";

import { LIMITS, type Flow } from "@/data";
import { ChipPicker } from "./ChipPicker";

/** Step 9. What the person can offer: the AI's suggestions chosen already, or the searchable list when it had none. */
export function Offers({ flow }: { flow: Flow }) {
  const saved = flow.answers.offers?.slugs as string[] | undefined;
  const suggested = flow.suggestions.offers;
  return (
    <ChipPicker
      flow={flow}
      title="Here's what you can offer."
      subhead={suggested.length ? "We picked these from what you wrote. Tap to remove or add back." : `Pick up to ${LIMITS.offers} things people can count on you for.`}
      limit={LIMITS.offers}
      suggested={suggested}
      initial={saved ?? suggested.slice(0, LIMITS.offers)}
      noun="skill"
      onSave={flow.actions.offers}
    />
  );
}
