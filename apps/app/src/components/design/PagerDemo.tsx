"use client";

import { Button, Chip, LargeTitleHeader, SegmentedControl, Sheet, TabBar, TabPager, TopBar, memberTabs, useTabSwipeLock, type PagerTab } from "@circuit/ui";
import { useMotionValue } from "motion/react";
import { useState } from "react";

const TABS = memberTabs({ circuits: true });

/** Long enough to scroll, so each tab can prove it keeps its scroll position. */
function Filler({ id }: { id: string }) {
  return (
    <ol className="flex flex-col gap-6 px-4 pb-8 pt-4">
      {Array.from({ length: 24 }, (_, i) => <li key={i} className="t-body text-text-muted">{id} · item {i + 1}</li>)}
    </ol>
  );
}

function Screen({ id, title, children }: { id: string; title: string; children?: React.ReactNode }) {
  return (
    <div data-demo-tab={id}>
      <TopBar title={title} mobileOnly />
      <LargeTitleHeader title={title} />
      {children}
      <Filler id={id} />
    </div>
  );
}

/** A row that scrolls sideways: a swipe that starts on it belongs to it, not to the pager. */
function ChipsRow() {
  return (
    <div data-testid="chips-row" className="no-scrollbar flex gap-2 overflow-x-auto px-4 py-2">
      {Array.from({ length: 20 }, (_, i) => <Chip key={i} label={`Skill ${i + 1}`} />)}
    </div>
  );
}

function MapLock() {
  useTabSwipeLock();
  return <div data-testid="map-area" className="mx-4 my-2 grid h-40 place-items-center rounded-card bg-surface t-body text-text-muted">The map owns every gesture here</div>;
}

function Discover() {
  const [seg, setSeg] = useState("people");
  return (
    <Screen id="discover" title="Discover">
      <div className="px-4 py-2"><SegmentedControl label="Discover" value={seg} onChange={setSeg} items={[{ id: "people", label: "People" }, { id: "map", label: "Map" }]} /></div>
      {seg === "map" && <MapLock />}
      <ChipsRow />
    </Screen>
  );
}

function Inbox({ onSheet }: { onSheet: () => void }) {
  return (
    <Screen id="inbox" title="Inbox">
      <div className="flex flex-col gap-3 px-4 py-2">
        <input aria-label="Search messages" placeholder="Search" className="min-h-11 rounded-control bg-surface-2 px-3 t-body" />
        <Button onClick={onSheet}>Open sheet</Button>
      </div>
    </Screen>
  );
}

export function PagerDemo() {
  const [value, setValue] = useState("home");
  const [sheet, setSheet] = useState(false);
  const [swipe, setSwipe] = useState(true);
  const progress = useMotionValue(0);
  const panes: PagerTab[] = [
    { id: "home", node: <Screen id="home" title="Today" /> },
    { id: "discover", node: <Discover /> },
    { id: "circuits", node: <Screen id="circuits" title="Circuits" /> },
    { id: "inbox", node: <Inbox onSheet={() => setSheet(true)} /> },
    { id: "profile", node: <Screen id="profile" title="Profile"><div className="px-4"><Button onClick={() => setSwipe((s) => !s)}>{swipe ? "Turn swiping off" : "Turn swiping on"}</Button></div></Screen> },
  ];
  return (
    <div data-page-behind>
      <div className="mx-auto w-full max-w-[600px] pb-[calc(88px+env(safe-area-inset-bottom))]">
        <TabPager tabs={panes} value={value} progress={progress} swipe={swipe} onSwipe={setValue} className="min-h-dvh overflow-x-clip" />
      </div>
      <TabBar tabs={TABS} active={value} progress={progress} onSelect={(id) => { if (id === value) window.scrollTo({ top: 0, behavior: "smooth" }); else setValue(id); }} />
      <Sheet open={sheet} onClose={() => setSheet(false)} title="A sheet" detent="medium">
        <p className="t-body text-text-muted">While this is open, swiping sideways does not change tabs.</p>
      </Sheet>
    </div>
  );
}
