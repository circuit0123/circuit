"use client";

import { Bell } from "lucide-react";
import { BarButton, ScreenBar } from "@circuit/ui";
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

/** Home (DESIGN.md §4): Live wire, Daily Drop, people worth meeting, Pulse. A feature that is off simply isn't here. */
export function Home() {
  const features = useFeatures();
  const desktop = useDesktop();
  const pulse = features.on("pulse");
  return (
    <>
      <ScreenBar wordmark={<span className="t-headline">Circuit</span>} right={<NotificationsBell />} mobileOnly />
      <h1 className="sr-only">Home</h1>
      {pulse && <div className="px-4 lg:px-0 lg:pt-6"><LiveWireSection /></div>}
      {features.on("daily_drop") && !desktop && <div className="px-4 pb-6 pt-2"><DropSection /></div>}
      {/* With a rail on desktop, People you may know lives there, unless Pulse is off and the column would be bare. */}
      {(!desktop || !pulse) && <MatchesSection className="px-4 pb-6 pt-2 lg:px-0" limit={desktop ? 8 : 5} offset={desktop ? 3 : 0} />}
      {pulse && <Pulse />}
    </>
  );
}
