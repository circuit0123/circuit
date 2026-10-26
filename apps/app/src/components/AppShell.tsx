"use client";

import { Bell, Plus } from "lucide-react";
import { Logo, TabBar, TabPager, cx, memberTabs, useToast, type PagerTab } from "@circuit/ui";
import { useMotionValue } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { composeHref, useFeatures, useMe, useNotificationNudges, useUnreadCount } from "@/data";
import { useDesktop } from "@/hooks/useDesktop";
import { Discover } from "./discover/Discover";
import { Home } from "./home/Home";
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
  const toast = useToast();
  const me = useMe().data;
  const unread = useUnreadCount().data ?? 0;
  useNotificationNudges();
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

  return (
    <div id="app-root" className="min-h-dvh">
      {/* Desktop left rail (Desktop.dc.html): the logo, the same destinations as the bar, then the one create button. */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col gap-1 border-r border-separator px-6 py-8 lg:flex" style={{ top: "var(--dev-bar, 0px)" }}>
        <Link href="/" aria-label="Circuit, Home" onClick={(e) => { e.preventDefault(); select("home"); }} className="mx-3 mb-8 flex items-center"><Logo kind="lockup" height={32} /></Link>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {tabs.map((t) => (
            <Link
              key={t.id}
              href={t.href}
              scroll={false}
              onClick={(e) => { e.preventDefault(); select(t.id); }}
              aria-current={t.id === active ? "page" : undefined}
              className={cx("flex h-12 items-center gap-4 rounded-control px-3 t-body", t.id === active ? "bg-surface font-semibold text-text" : "text-text-muted")}
            >
              {t.icon}
              {t.label}
            </Link>
          ))}
        </nav>
        {features.on("pulse") && (
          <button type="button" onClick={() => (composeHref ? router.push(composeHref) : toast({ text: "The build log composer is coming next." }))} className="mt-6 flex h-11 items-center justify-center gap-2 rounded-control bg-surface-2 t-body font-medium active:scale-[0.97]">
            <Plus size={20} strokeWidth={1.8} aria-hidden />New build log
          </button>
        )}
        <Link href="/notifications" aria-label={unread > 0 ? `Notifications, ${unread > 9 ? "9+" : unread} unread` : "Notifications"} className={cx("mt-auto flex h-12 items-center gap-4 rounded-control px-3 t-body", path === "/notifications" ? "bg-surface font-semibold text-text" : "text-text-muted")}>
          <span className="relative flex"><Bell size={24} strokeWidth={1.75} aria-hidden />{unread > 0 && <span className="absolute -right-0.5 top-0 h-2 w-2 rounded-full bg-live ring-2 ring-bg" aria-hidden />}</span>
          Notifications
        </Link>
      </aside>

      <div className="lg:pl-60">
        <div className="mx-auto flex w-full max-w-[1092px] justify-center lg:gap-14 lg:px-12">
          <main data-page-behind className="w-full min-w-0 overflow-x-clip pb-[calc(88px+env(safe-area-inset-bottom))] pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)] lg:max-w-[600px] lg:p-0 lg:pb-12">
            <TabPager className={pushed ? undefined : "min-h-dvh overflow-x-clip"} tabs={panes} value={active} progress={progress} swipe={!!me?.appearance.swipeTabs && !desktop && !pushed} onSwipe={(id) => select(id)} />
            {pushed && children}
          </main>
          {!pushed && desktop && active === "home" && <HomeRail />}
        </div>
      </div>

      {!pushed && <TabBar tabs={tabs} active={active} progress={progress} onSelect={select} />}
    </div>
  );
}
