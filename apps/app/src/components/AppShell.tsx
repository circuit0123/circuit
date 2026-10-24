"use client";

import { CircleDot, Compass, Home as HomeIcon, MessageCircle, UserRound } from "lucide-react";
import { TabBar, TabPager, cx, type PagerTab, type TabItem } from "@circuit/ui";
import { useMotionValue } from "motion/react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useFeatures, useMe, useUnreadCount } from "@/data";
import { useDesktop } from "@/hooks/useDesktop";
import { DevBar } from "./DevBar";
import { Discover } from "./discover/Discover";
import { Home, NotificationsBell } from "./home/Home";
import { HomeRail } from "./home/Rail";
import { Inbox } from "./inbox/Inbox";
import { Profile } from "./profile/Profile";

type Def = { id: string; label: string; href: string; Icon: typeof HomeIcon; node: React.ReactNode; feature?: "circuits" };

/** All tabs the app can draw, in bar order. `circuits` has no screens yet, so the features hook keeps it hidden. */
const DEFS: Def[] = [
  { id: "home", label: "Home", href: "/", Icon: HomeIcon, node: <Home /> },
  { id: "discover", label: "Discover", href: "/discover", Icon: Compass, node: <Discover /> },
  { id: "circuits", label: "Circuits", href: "/circuits", Icon: CircleDot, node: null, feature: "circuits" },
  { id: "inbox", label: "Inbox", href: "/inbox", Icon: MessageCircle, node: <Inbox /> },
  { id: "profile", label: "Profile", href: "/profile", Icon: UserRound, node: <Profile /> },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const features = useFeatures();
  const me = useMe().data;
  const unread = useUnreadCount().data ?? 0;
  const desktop = useDesktop();
  const path = usePathname();
  const router = useRouter();

  const defs = DEFS.filter((d) => !d.feature || features.on(d.feature));
  const fromPath = defs.find((d) => d.href === path)?.id ?? null;
  const [picked, setPicked] = useState<string | null>(fromPath);
  useEffect(() => { setPicked(fromPath); }, [fromPath]); // eslint-disable-line react-hooks/set-state-in-effect
  const active = fromPath === null ? null : picked;
  const progress = useMotionValue(Math.max(0, defs.findIndex((d) => d.id === active)));

  const select = (id: string) => {
    const d = defs.find((x) => x.id === id);
    if (!d) return;
    if (id === active) { window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    setPicked(id);
    router.push(d.href, { scroll: false });
  };

  const tabs: TabItem[] = defs.map((d) => ({ id: d.id, label: d.label, href: d.href, icon: <d.Icon size={24} strokeWidth={1.75} aria-hidden />, dot: d.id === "inbox" ? false : undefined }));
  const panes: PagerTab[] = defs.map((d) => ({ id: d.id, node: d.node }));
  const pushed = active === null;
  const rail = !pushed && desktop && active === "home" ? <HomeRail showMatches={features.on("pulse")} /> : null;

  return (
    <div className="min-h-dvh">
      <DevBar />
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
        <div className="mx-auto flex w-full max-w-[1000px] justify-center gap-10 lg:px-6">
          <main className="w-full min-w-0 overflow-x-clip pb-24 lg:max-w-[600px] lg:pb-12">
            <TabPager className="min-h-dvh overflow-x-clip" tabs={panes} value={active} progress={progress} swipe={!!me?.appearance.swipeTabs && !desktop && !pushed} onSwipe={(id) => select(id)} />
            {pushed && children}
          </main>
          {rail && <aside aria-label="For you" className="sticky hidden w-80 shrink-0 self-start py-6 lg:block" style={{ top: "var(--dev-bar, 0px)" }}>{rail}</aside>}
        </div>
      </div>

      {!pushed && <TabBar tabs={tabs} active={active} progress={progress} onSelect={select} />}
    </div>
  );
}
