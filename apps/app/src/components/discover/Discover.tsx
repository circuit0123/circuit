"use client";

import { EmptyState, Screen, Section } from "@circuit/ui";
import { MatchesSection } from "../home/MatchesSection";

/** Discover (DESIGN.md §4): people first. Jobs (with "Skills in demand" on top), Startups and the Map arrive with their own steps. */
export function Discover() {
  return (
    <Screen title="Discover">
      {/* Offset 3: the Daily Drop on Home already shows the first three matches. */}
      <MatchesSection title="People you may know" limit={8} offset={3} />
      <Section><EmptyState text="Jobs and the map arrive in the next step." /></Section>
    </Screen>
  );
}
