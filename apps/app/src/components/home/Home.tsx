"use client";

import { Bell } from "lucide-react";
import { Screen, Section } from "@circuit/ui";
import Link from "next/link";
import { useFeatures, useUnreadCount } from "@/data";
import { useDesktop } from "@/hooks/useDesktop";
import { DropSection } from "./DropSection";
import { LiveWireSection } from "./LiveWireSection";
import { MatchesSection } from "./MatchesSection";
import { Pulse } from "./Pulse";

export function NotificationsBell() {
  const unread = useUnreadCount().data ?? 0;
  return (
    <Link href="/notifications" aria-label={unread > 0 ? `Notifications, ${unread > 9 ? "9+" : unread} unread` : "Notifications"} className="relative flex h-11 w-11 items-center justify-center rounded-full active:opacity-80">
      <Bell size={24} strokeWidth={1.75} />
      {unread > 0 && <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full bg-live ring-2 ring-bg" aria-hidden />}
    </Link>
  );
}

/** Home (DESIGN.md §4): a `Today` title, then the Live wire, the Daily Drop (in the right rail on desktop) and Pulse. A feature that is off simply isn't here. */
export function Home() {
  const features = useFeatures();
  const desktop = useDesktop();
  const pulse = features.on("pulse");
  return (
    <Screen title="Today" right={<NotificationsBell />}>
      {pulse && <Section><LiveWireSection /></Section>}
      {features.on("daily_drop") && !desktop && <Section><DropSection /></Section>}
      {/* People you may know lives in Discover. Only when Pulse is off would Home be bare, so then it carries the matches. */}
      {!pulse && <MatchesSection limit={desktop ? 8 : 5} offset={desktop ? 3 : 0} />}
      {pulse && <Pulse />}
    </Screen>
  );
}
