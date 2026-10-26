"use client";

import { useHome } from "@/data";
import { DropSection } from "./DropSection";

/** Desktop right rail on Home: the Daily Drop and nothing else (DESIGN.md §3). With Pulse off the drop is the centre column instead, so there is no rail. */
export function HomeRail() {
  const home = useHome();
  if (!(home.ready && home.drop && home.pulse)) return null;
  return (
    <aside aria-label="For you" className="sticky hidden w-[340px] shrink-0 self-start py-6 lg:block" style={{ top: "var(--dev-bar, 0px)" }}>
      <DropSection />
    </aside>
  );
}
