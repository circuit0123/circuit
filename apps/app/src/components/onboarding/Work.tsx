"use client";

import { Button, Step, TextArea } from "@circuit/ui";
import { useState } from "react";
import { type Flow, useMe } from "@/data";

/** Step 8. One big field; the AI reads it on Continue and the next screen shows what it found. Skip goes to the pickers. */
export function Work({ flow }: { flow: Flow }) {
  const me = useMe().data;
  const [text, setText] = useState(me?.bio ?? "");
  const submit = () => void flow.actions.work(text);
  return (
    <Step
      title="What are you working on?"
      subhead="Paste your bio, LinkedIn About, or just tell us in a few lines."
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      onSkip={flow.saving ? undefined : () => void flow.actions.work(null)}
      footer={
        <>
          {flow.error && <p role="alert" className="t-footnote text-danger">{flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={flow.saving} onClick={submit}>{flow.saving ? "Reading what you wrote…" : "Continue"}</Button>
        </>
      }
    >
      <TextArea
        label="About your work"
        hideLabel
        autoFocus
        maxLength={2000}
        placeholder="I'm a third-year student who builds…"
        value={text}
        onChange={(e) => setText(e.target.value)}
        // Enter makes a new line here; Ctrl or ⌘ + Enter sends it.
        onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); } }}
        hint="We use this only to suggest your skills. You'll confirm everything next."
      />
    </Step>
  );
}
