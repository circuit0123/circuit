"use client";

import { AddChip, Button, Chip, ErrorState, SearchField, Sheet, Skeleton, Step } from "@circuit/ui";
import { useMemo, useState } from "react";
import { type Flow, useCapabilities } from "@/data";

type Props = {
  flow: Flow;
  title: string;
  subhead: string;
  /** Most chips that can be chosen (Offers 5, Needs 3). */
  limit: number;
  /** What the AI read from the bio. Empty means: show the whole searchable list instead. */
  suggested: string[];
  /** What is chosen when the screen opens: the saved answer if there is one, otherwise the suggestions. */
  initial: string[];
  /** One word for the footnote and the labels: "skill" → "Add a skill". */
  noun: string;
  onSave: (slugs: string[]) => Promise<boolean>;
};

/**
 * Steps 9 and 10. With AI suggestions: chips start chosen, tap to remove or add back, "+ Add" searches the rest. Without: the whole list of
 * capabilities with a search field, and no error shown (DESIGN.md §4). Counted against a limit; at least one is needed to go on.
 */
export function ChipPicker({ flow, title, subhead, limit, suggested, initial, noun, onSave }: Props) {
  const caps = useCapabilities();
  const names = useMemo(() => new Map((caps.data ?? []).map((c) => [c.slug, c.name])), [caps.data]);
  const known = (slugs: string[]) => slugs.filter((s) => names.has(s));

  const ai = suggested.length > 0;
  const [chosen, setChosen] = useState<string[]>(() => initial);
  // The chips on show in the suggested layout: what the AI found, what was saved before, and anything added from the sheet.
  const [extra, setExtra] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [adding, setAdding] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const picked = known(chosen);
  const shown = [...new Set([...suggested, ...initial, ...extra])].filter((s) => names.has(s));
  const atLimit = picked.length >= limit;

  const toggle = (slug: string) => {
    setNote(null);
    if (chosen.includes(slug)) { setChosen(chosen.filter((s) => s !== slug)); return; }
    if (atLimit) { setNote(`Up to ${limit}. Remove one to add another.`); return; }
    setChosen([...chosen, slug]);
  };
  const add = (slug: string) => {
    setExtra([...extra, slug]);
    setChosen([...chosen, slug]);
    setNote(null);
    setAdding(false);
    setQuery("");
  };
  const submit = () => {
    if (picked.length === 0) { setNote("Pick at least one."); return; }
    void onSave(picked);
  };

  const matches = (all: Array<{ slug: string; name: string }>) => {
    const q = query.trim().toLowerCase();
    return all.filter((c) => !q || c.name.toLowerCase().includes(q));
  };
  const everything = caps.data ?? [];

  return (
    <Step
      title={title}
      subhead={subhead}
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      footer={
        <>
          {flow.error && <p role="alert" className="t-footnote text-danger">{flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={flow.saving} onClick={submit}>Continue</Button>
        </>
      }
    >
      {caps.isError ? (
        <ErrorState text="Couldn't load the list." onRetry={() => void caps.refetch()} />
      ) : !caps.data ? (
        <div className="flex flex-wrap gap-2.5" aria-busy="true">{["w-24", "w-32", "w-20", "w-28", "w-26", "w-22"].map((w) => <Skeleton key={w} round className={`h-10 ${w}`} />)}</div>
      ) : ai ? (
        <>
          <div role="group" aria-label={`Your ${noun}s`} className="flex flex-wrap gap-2.5">
            {shown.map((s) => <Chip key={s} size="lg" label={names.get(s) ?? s} selected={picked.includes(s)} onToggle={() => toggle(s)} />)}
            <AddChip label={`Add a ${noun}`} onClick={() => (atLimit ? setNote(`Up to ${limit}. Remove one to add another.`) : setAdding(true))} />
          </div>
          <Sheet open={adding} onClose={() => { setAdding(false); setQuery(""); }} title={`Add a ${noun}`} detent="large" detents={["large"]}>
            <SearchField aria-label={`Search ${noun}s`} placeholder={`Search ${noun}s`} value={query} onChange={(e) => setQuery(e.target.value)} />
            <ul className="mt-2">
              {matches(everything.filter((c) => !shown.includes(c.slug))).map((c) => (
                <li key={c.slug}>
                  <button type="button" onClick={() => add(c.slug)} className="flex min-h-14 w-full items-center t-body active:opacity-80">{c.name}</button>
                </li>
              ))}
              {matches(everything.filter((c) => !shown.includes(c.slug))).length === 0 && <li className="t-body py-4 text-text-muted">Nothing matches that.</li>}
            </ul>
          </Sheet>
        </>
      ) : (
        <>
          <SearchField aria-label={`Search ${noun}s`} placeholder={`Search ${noun}s`} value={query} onChange={(e) => setQuery(e.target.value)} />
          <div role="group" aria-label={`Your ${noun}s`} className="mt-4 flex flex-wrap gap-2.5">
            {matches(everything).map((c) => <Chip key={c.slug} size="lg" label={c.name} selected={picked.includes(c.slug)} onToggle={() => toggle(c.slug)} />)}
            {matches(everything).length === 0 && <p className="t-body text-text-muted">Nothing matches that.</p>}
          </div>
        </>
      )}
      <p className="num t-footnote mt-5 text-text-subtle">{picked.length} of {limit}</p>
      {note && <p role="status" className="t-footnote mt-2 text-text-muted">{note}</p>}
    </Step>
  );
}
