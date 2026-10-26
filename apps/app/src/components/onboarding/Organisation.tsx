"use client";

import { SearchField, Step } from "@circuit/ui";
import { useState } from "react";
import { type Flow, useOrganisationSearch } from "@/data";
import { ChoiceRow } from "./ChoiceRow";

/** Step 11 (students). A tap on a result advances; a college that isn't listed is fine, so what was typed can be used as it is. */
export function Organisation({ flow }: { flow: Flow }) {
  const [query, setQuery] = useState("");
  const found = useOrganisationSearch(query);
  const typed = query.trim();
  const exact = found.some((o) => o.toLowerCase() === typed.toLowerCase());
  return (
    <Step
      title="Where do you study?"
      subhead="We'll show you people and roles from your campus."
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      onSkip={flow.saving ? undefined : () => void flow.actions.organisation(null)}
    >
      <SearchField aria-label="Search colleges" placeholder="Search your college" autoFocus value={query} onChange={(e) => setQuery(e.target.value)} />
      <div className="mt-4 flex flex-col gap-3">
        {found.map((o) => <ChoiceRow key={o} label={o} chevron={false} disabled={flow.saving} onClick={() => void flow.actions.organisation(o)} />)}
        {typed.length >= 2 && !exact && <ChoiceRow label={`Use “${typed}”`} chevron={false} disabled={flow.saving} onClick={() => void flow.actions.organisation(typed)} />}
      </div>
      {flow.error && <p role="alert" className="t-footnote mt-4 text-danger">{flow.error}</p>}
    </Step>
  );
}
