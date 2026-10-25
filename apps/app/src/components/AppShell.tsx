"use client";

import { TabBar, TabPager, cx, memberTabs, type PagerTab } from "@circuit/ui";
import { useMotionValue } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useFeatures, useMe, useUnreadCount } from "@/data";
import { useDesktop } from "@/hooks/useDesktop";
import { Discover } from "./discover/Discover";
import { Home, NotificationsBell } from "./home/Home";
import { HomeRail } from "./home/Rail";
import { Inbox } from "./inbox/Inbox";
import { Profile } from "./profile/Profile";

/** The screen behind each tab id. A tab with no screens yet (Circuits, until its session) has no node, so the features hook keeps it hidden. */
const NODES: Record<string, React.ReactNode> = {
  home: <Home />,
  discover: <Discover />,
  circuits: null,
  inbox: <Inbox />,
  profile: <Profile />,
};

export function AppShell({ children }: { children: React.ReactNode }) {
  const features = useFeatures();
  const me = useMe().data;
  const unread = useUnreadCount().data ?? 0;
  const desktop = useDesktop();
  const path = usePathname();
  const router = useRouter();

  // Bar order and labels come from the shared preset. `features.on` is false for anything the server has off or the app has no screens for.
  const tabs = memberTabs({ circuits: features.on("circuits"), inboxDot: false });
  const fromPath = tabs.find((t) => t.href === path)?.id ?? null;
  const [picked, setPicked] = useState<string | null>(fromPath);
  useEffect(() => { setPicked(fromPath); }, [fromPath]); // eslint-disable-line react-hooks/set-state-in-effect
  const active = fromPath === null ? null : picked;
  const progress = useMotionValue(Math.max(0, tabs.findIndex((t) => t.id === active)));

  const select = (id: string) => {
    const d = tabs.find((x) => x.id === id);
    if (!d) return;
    if (id === active) { window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    setPicked(id);
    router.push(d.href, { scroll: false });
  };

  const panes: PagerTab[] = tabs.map((t) => ({ id: t.id, node: NODES[t.id] }));
  const pushed = active === null;
  const rail = !pushed && desktop && active === "home" ? <HomeRail /> : null;

  return (
    <div id="app-root" className="min-h-dvh">
      {/* Desktop left rail: the same destinations as the bar. */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col gap-2 border-r border-separator px-4 py-6 lg:flex" style={{ top: "var(--dev-bar, 0px)" }}>
        <Link href="/" className="t-title2 mb-6 px-3">Circuit</Link>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {tabs.map((t) => (
            <Link
              key={t.id}
              href={t.href}
              scroll={false}
              onClick={(e) => { e.preventDefault(); select(t.id); }}
              aria-current={t.id === active ? "page" : undefined}
              className={cx("flex min-h-12 items-center gap-4 rounded-control px-3 t-body", t.id === active ? "font-semibold text-text" : "text-text-muted")}
            >
              {t.icon}
              {t.label}
            </Link>
          ))}
        </nav>
        <div className="mt-auto flex items-center justify-between">
          <NotificationsBell />
          {unread > 0 && <span className="sr-only">{unread} unread</span>}
        </div>
      </aside>

      <div className="lg:pl-60">
        <div className="mx-auto flex w-full max-w-[1036px] justify-center gap-12 lg:px-6">
          <main data-page-behind className="w-full min-w-0 overflow-x-clip pb-[calc(88px+env(safe-area-inset-bottom))] pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)] lg:max-w-[600px] lg:p-0 lg:pb-12">
            <TabPager className="min-h-dvh overflow-x-clip" tabs={panes} value={active} progress={progress} swipe={!!me?.appearance.swipeTabs && !desktop && !pushed} onSwipe={(id) => select(id)} />
            {pushed && children}
          </main>
          {rail && <aside aria-label="For you" className="sticky hidden w-[340px] shrink-0 self-start py-6 lg:block" style={{ top: "var(--dev-bar, 0px)" }}>{rail}</aside>}
        </div>
      </div>

      {!pushed && <TabBar tabs={tabs} active={active} progress={progress} onSelect={select} />}
    </div>
  );
}
