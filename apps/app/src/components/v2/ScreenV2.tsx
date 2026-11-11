"use client";

import { BigHeadline, IconButton, LogoV2 } from "@circuit/ui";
import { Bell, SlidersHorizontal } from "lucide-react";
import Link from "next/link";
import { useUnreadCount } from "@/data";

/** Header row of the PM tab screens: logo on the left, settings and notifications on the right (PMHome.dc.html). */
export function HeaderV2() {
  const unread = useUnreadCount().data ?? 0;
  return (
    <header className="flex items-center justify-between px-5 pt-[calc(20px+env(safe-area-inset-top))] lg:pt-6">
      <LogoV2 height={23} className="lg:hidden" />
      <div className="flex gap-2 lg:ml-auto">
        <Link href="/settings" aria-label="Settings" className="flex h-10 w-10 items-center justify-center rounded-full border border-c-border bg-c-card text-c-text">
          <SlidersHorizontal size={18} strokeWidth={1.9} aria-hidden />
        </Link>
        <Link href="/notifications" aria-label={unread > 0 ? `Notifications, ${unread > 9 ? "9+" : unread} unread` : "Notifications"} className="relative flex h-10 w-10 items-center justify-center rounded-full border border-c-border bg-c-card text-c-text">
          <Bell size={18} strokeWidth={1.8} aria-hidden />
          {unread > 0 && <span aria-hidden className="absolute right-[9px] top-2 h-[7px] w-[7px] rounded-full bg-c-bright" />}
        </Link>
      </div>
    </header>
  );
}

/** A v2 tab screen: header, the one big headline, then the content. */
export function ScreenV2({ first, second, children }: { first: string; second?: string; children: React.ReactNode }) {
  return (
    <div className="bg-c-bg text-c-text">
      <HeaderV2 />
      <BigHeadline first={first} second={second} className="mx-5 mt-5" />
      {children}
    </div>
  );
}

export { IconButton };
