"use client";

import { Button, SearchField, Sheet, Step } from "@circuit/ui";
import { useState } from "react";
import { type Flow, useWhere } from "@/data";

/** Step 7. A coarse location only: the phone's position rounded to about 1 km, or the centre of a chosen city. */
export function Where({ flow }: { flow: Flow }) {
  const { cities, locate } = useWhere();
  const [finding, setFinding] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [choosing, setChoosing] = useState(false);
  const [query, setQuery] = useState("");

  const locateMe = async () => {
    setNote(null);
    setFinding(true);
    const r = await locate();
    setFinding(false);
    if (!r.ok) { setNote(r.reason === "denied" ? "Location is off. Choose a city instead." : "Couldn't find you. Choose a city instead."); return; }
    await flow.actions.where(r.place);
  };
  const shown = cities.filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase()));
  const busy = finding || flow.saving;

  return (
    <Step
      title="Where are you based?"
      subhead="We only keep a rough area, never your address."
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      footer={
        <>
          {(note || flow.error) && <p role="alert" className="t-footnote text-danger">{note ?? flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={busy} onClick={() => void locateMe()}>{finding ? "Finding you…" : "Use my location"}</Button>
          <Button variant="text" className="w-full" disabled={busy} onClick={() => setChoosing(true)}>Choose a city</Button>
        </>
      }
    >
      <Sheet open={choosing} onClose={() => setChoosing(false)} title="Choose a city" detent="large" detents={["large"]}>
        <SearchField aria-label="Search cities" placeholder="Search cities" value={query} onChange={(e) => setQuery(e.target.value)} />
        <ul className="mt-2">
          {shown.map((c) => (
            <li key={c.name}>
              <button
                type="button"
                disabled={flow.saving}
                onClick={async () => { if (await flow.actions.where({ lat: c.lat, lng: c.lng, city: c.name })) setChoosing(false); }}
                className="flex min-h-14 w-full items-center t-body active:opacity-80"
              >
                {c.name}
              </button>
            </li>
          ))}
          {shown.length === 0 && <li className="t-body py-4 text-text-muted">No city matches that.</li>}
        </ul>
      </Sheet>
    </Step>
  );
}
