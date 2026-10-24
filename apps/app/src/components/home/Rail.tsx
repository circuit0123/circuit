"use client";

import { useFeatures } from "@/data";
import { DropSection } from "./DropSection";

/** Desktop right rail on Home: the Daily Drop and nothing else (DESIGN.md §3). */
export function HomeRail() {
  const features = useFeatures();
  return features.on("daily_drop") ? <DropSection /> : null;
}
