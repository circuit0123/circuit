"use client";

import { notFound } from "next/navigation";
import { useFeatures } from "@/data";

/** With `circuits` off there is no tab, so a deep link to /circuits shows the normal 404 screen (DESIGN.md §3). */
export function CircuitsRoute() {
  const features = useFeatures();
  if (features.ready && !features.on("circuits")) notFound();
  return null;
}
