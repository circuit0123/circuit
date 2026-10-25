"use client";

import { Button, Step, TextField } from "@circuit/ui";
import { useState } from "react";
import { type Flow, useMe, useSession } from "@/data";

/** Step 4. Prefilled from what Google told us, so most people just tap Continue. */
export function Name({ flow }: { flow: Flow }) {
  const { identity } = useSession();
  const me = useMe().data;
  const saved = flow.answers.name as { first?: string; last?: string } | undefined;
  const [guessFirst, ...guessRest] = (identity?.name || me?.name || "").split(/\s+/).filter(Boolean);
  const [first, setFirst] = useState(saved?.first ?? guessFirst ?? "");
  const [last, setLast] = useState(saved?.last ?? guessRest.join(" "));
  const [missing, setMissing] = useState<string | null>(null);
  const submit = () => {
    if (!first.trim()) { setMissing("Add your first name."); return; }
    void flow.actions.name(first, last);
  };
  return (
    <Step
      title="What should we call you?"
      subhead="Use the name people know you by."
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      footer={
        <>
          {flow.error && <p role="alert" className="t-footnote text-danger">{flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={flow.saving} onClick={submit}>Continue</Button>
        </>
      }
    >
      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="flex flex-col gap-4">
        <TextField label="First name" autoComplete="given-name" autoFocus value={first} onChange={(e) => { setFirst(e.target.value); setMissing(null); }} error={missing} maxLength={60} />
        <TextField label="Last name" autoComplete="family-name" value={last} onChange={(e) => setLast(e.target.value)} maxLength={60} />
        <button type="submit" hidden />
      </form>
    </Step>
  );
}
