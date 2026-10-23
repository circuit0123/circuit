"use client";

import { useDesktop } from "@/hooks/useDesktop";
import { AppShell } from "../AppShell";
import { DropSection } from "./DropSection";
import { Pulse } from "./Pulse";
import { Rail } from "./Rail";
import { TodaySection } from "./TodaySection";

export function Home() {
  const desktop = useDesktop();
  return (
    <AppShell rail={desktop ? <Rail /> : null}>
      <h1 className="sr-only">Home</h1>
      <div className="px-4 lg:px-0"><TodaySection /></div>
      {!desktop && <div className="px-4 pb-6 pt-2"><DropSection /></div>}
      <Pulse />
    </AppShell>
  );
}
