"use client";

import { Button, Chip, Sheet } from "@circuit/ui";
import { useEffect, useState } from "react";
import { FILTERS_FOR, NO_FILTERS, useCapabilities, type DiscoverFilters, type Segment } from "@/data";

const DISTANCES: Array<{ v: number | null; label: string }> = [{ v: null, label: "Any distance" }, { v: 5, label: "Within 5 km" }, { v: 10, label: "Within 10 km" }, { v: 25, label: "Within 25 km" }];
const ROLES: Array<{ v: DiscoverFilters["role"]; label: string }> = [{ v: null, label: "Everyone" }, { v: "student", label: "Students" }, { v: "founder", label: "Founders" }, { v: "mentor", label: "Mentors" }];
const KINDS: Array<{ v: DiscoverFilters["kind"]; label: string }> = [{ v: null, label: "Any type" }, { v: "internship", label: "Internship" }, { v: "full_time", label: "Full time" }, { v: "part_time", label: "Part time" }];

/** Filters in a bottom sheet (DESIGN.md §4 Discover): only the ones this segment can use. Nothing changes until "Show results". */
export function FilterSheet({ open, onClose, segment, value, onApply }: { open: boolean; onClose: () => void; segment: Segment; value: DiscoverFilters; onApply: (f: DiscoverFilters) => void }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => { if (open) setDraft(value); }, [open, value]); // eslint-disable-line react-hooks/set-state-in-effect
  const caps = useCapabilities();
  const has = (k: keyof DiscoverFilters) => FILTERS_FOR[segment].includes(k);
  const set = (p: Partial<DiscoverFilters>) => setDraft((d) => ({ ...d, ...p }));

  return (
    <Sheet open={open} onClose={onClose} title="Filters" detent="large">
      <div className="flex flex-col gap-8 pt-2">
        {has("distanceKm") && (
          <Group label="Distance">
            {DISTANCES.map((d) => <Chip key={d.label} label={d.label} selected={draft.distanceKm === d.v} onToggle={() => set({ distanceKm: d.v })} />)}
          </Group>
        )}
        {has("role") && (
          <Group label="Who">
            {ROLES.map((r) => <Chip key={r.label} label={r.label} selected={draft.role === r.v} onToggle={() => set({ role: r.v })} />)}
          </Group>
        )}
        {has("kind") && (
          <Group label="Type">
            {KINDS.map((k) => <Chip key={k.label} label={k.label} selected={draft.kind === k.v} onToggle={() => set({ kind: k.v })} />)}
          </Group>
        )}
        {has("capability") && (
          <label className="flex flex-col gap-2">
            <span className="t-headline">Skill</span>
            <select
              value={draft.capability ?? ""}
              onChange={(e) => set({ capability: e.target.value || null })}
              className="min-h-12 rounded-control bg-surface-2 px-3 t-body text-text"
            >
              <option value="">Any skill</option>
              {(caps.data ?? []).map((c) => <option key={c.slug} value={c.slug}>{c.name}</option>)}
            </select>
          </label>
        )}
        {(has("hiringOnly") || has("verifiedOnly")) && (
          <Group label="Show only">
            {has("hiringOnly") && <Chip label="Hiring" selected={draft.hiringOnly} onToggle={() => set({ hiringOnly: !draft.hiringOnly })} />}
            {has("verifiedOnly") && <Chip label="Verified" selected={draft.verifiedOnly} onToggle={() => set({ verifiedOnly: !draft.verifiedOnly })} />}
          </Group>
        )}
        <div className="flex flex-col gap-2">
          <Button variant="primary" className="w-full" onClick={() => { onApply(draft); onClose(); }}>Show results</Button>
          <Button variant="text" className="w-full" onClick={() => setDraft({ ...draft, ...Object.fromEntries(FILTERS_FOR[segment].map((k) => [k, NO_FILTERS[k]])) })}>Clear filters</Button>
        </div>
      </div>
    </Sheet>
  );
}

function Group({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="t-headline mb-3">{label}</legend>
      <div className="flex flex-wrap gap-2">{children}</div>
    </fieldset>
  );
}
