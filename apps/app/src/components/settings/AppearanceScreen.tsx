"use client";

import { AccentPicker, GroupedList, ListRow, SegmentedControl, Skeleton, Toggle, type Theme } from "@circuit/ui";
import { useAppearance } from "@/data";
import { ROW_INSET } from "../sheets";
import { SettingsScreen } from "./SettingsHome";

const THEMES: Array<{ id: Theme; label: string }> = [{ id: "system", label: "System" }, { id: "dark", label: "Dark" }, { id: "light", label: "Light" }];

/**
 * Appearance (Appearance.dc.html, DESIGN.md §5): theme, your colour with a live preview, and swipe between tabs. Each change shows at once
 * (the theme provider crossfades) and is saved on the member, so it follows you to every device.
 */
export function AppearanceScreen() {
  const { appearance: a, save } = useAppearance();
  return (
    <SettingsScreen title="Appearance">
      {!a ? (
        <div className="flex flex-col gap-7 px-4 lg:px-0" aria-label="Loading appearance"><Skeleton className="h-9" /><Skeleton className="h-40" /></div>
      ) : (
        <>
          <section aria-labelledby="theme-h" className="px-4 lg:px-0">
            <h2 id="theme-h" className="t-headline mb-2">Theme</h2>
            <SegmentedControl stretch label="Theme" items={THEMES} value={a.theme} onChange={(theme) => save.mutate({ theme })} />
          </section>
          <section aria-labelledby="colour-h" className="mt-3 px-4 lg:px-0">
            <h2 id="colour-h" className="t-headline">Your colour</h2>
            <p className="t-subhead mb-5 mt-1 text-text-muted">Marks what&apos;s live and new. Buttons stay neutral.</p>
            <AccentPicker value={a.accent} onChange={(accent) => save.mutate({ accent })} previewText="Divya shipped offline sync" />
          </section>
          <GroupedList footer="Swipe left or right anywhere on a tab to move to the next one. It's off when Reduce motion is on.">
            <ListRow className={ROW_INSET} title="Swipe between tabs" trailing={<Toggle label="Swipe between tabs" checked={a.swipeTabs} onChange={(swipeTabs) => save.mutate({ swipeTabs })} />} />
          </GroupedList>
          {save.isError && <p role="alert" className="t-footnote px-4 text-danger lg:px-0">Couldn&apos;t save that. Check your connection and try again.</p>}
        </>
      )}
    </SettingsScreen>
  );
}
