"use client";

import { Avatar, MatchStrength, Skeleton } from "@circuit/ui";
import { useMorePeople } from "@/hooks/home";
import { DropSection } from "./DropSection";

/** Desktop right rail: the Daily Drop and a few more people. */
export function Rail() {
  const more = useMorePeople();
  return (
    <div className="flex flex-col gap-8">
      <DropSection />
      <section aria-label="People you may know">
        <h2 className="t-headline mb-2">People you may know</h2>
        {more.isPending && <Skeleton className="h-32" />}
        <ul className="divide-y divide-border">
          {more.data?.items.map((m) => (
            <li key={m.candidate_id} className="flex items-center gap-3 py-3">
              <Avatar id={m.candidate_id} name={m.display_name} size={40} />
              <div className="min-w-0 flex-1">
                <p className="t-body truncate font-semibold">{m.display_name}</p>
                <p className="t-caption truncate text-text-muted">{m.city}</p>
              </div>
              <MatchStrength strength={m.strength} />
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
