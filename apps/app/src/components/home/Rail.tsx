"use client";

import { useFeatures } from "@/data";
import { DropSection } from "./DropSection";
import { MatchesSection } from "./MatchesSection";

/** Desktop right rail on Home: the Daily Drop, then a few more people (DESIGN.md §3). */
export function HomeRail({ showMatches }: { showMatches: boolean }) {
  const features = useFeatures();
  return (
    <div className="flex flex-col gap-8">
      {features.on("daily_drop") && <DropSection />}
      {showMatches && <MatchesSection limit={3} offset={3} title="People you may know" />}
    </div>
  );
}
