"use client";

import { Compass, Home, LayoutDashboard, MessageCircle, UserRound } from "lucide-react";
import { motion, useTransform, type MotionValue } from "motion/react";
import { cx } from "./cx";

export type TabItem = { id: string; label: string; href: string; icon: React.ReactNode; dot?: boolean };

/** The Circuits mark from TabBar.dc.html: a ring with three nodes, drawn in Lucide's style (24px grid, outline, round caps). */
export function CircuitsIcon({ size = 24, strokeWidth = 1.75 }: { size?: number; strokeWidth?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <circle cx="12" cy="12" r="7.5" />
      <circle cx="12" cy="4.5" r="1.8" fill="var(--bg)" />
      <circle cx="5.5" cy="15.8" r="1.8" fill="var(--bg)" />
      <circle cx="18.5" cy="15.8" r="1.8" fill="var(--bg)" />
    </svg>
  );
}

const icon = { size: 24, strokeWidth: 1.75, "aria-hidden": true } as const;

type PresetOptions = {
  /** Circuits is off for this member (flag off, or no screens yet): the bar has four tabs and swiping follows them (DESIGN.md §3). */
  circuits?: boolean;
  /** A dot on Inbox when something is unread. */
  inboxDot?: boolean;
};

/** Home · Discover · Circuits · Inbox · Profile. A feature that is off isn't greyed out; it is simply not in the list. */
export function memberTabs({ circuits = true, inboxDot }: PresetOptions = {}): TabItem[] {
  return [
    { id: "home", label: "Home", href: "/", icon: <Home {...icon} /> },
    { id: "discover", label: "Discover", href: "/discover", icon: <Compass {...icon} /> },
    ...(circuits ? [{ id: "circuits", label: "Circuits", href: "/circuits", icon: <CircuitsIcon /> }] : []),
    { id: "inbox", label: "Inbox", href: "/inbox", icon: <MessageCircle {...icon} />, dot: inboxDot },
    { id: "profile", label: "Profile", href: "/profile", icon: <UserRound {...icon} /> },
  ];
}

/** Partner admins get Dashboard in the third place; Circuits moves into Profile → Activity (DESIGN.md §3). */
export function partnerTabs({ inboxDot }: Pick<PresetOptions, "inboxDot"> = {}): TabItem[] {
  const [home, discover, , inbox, profile] = memberTabs({ inboxDot });
  return [home, discover, { id: "dashboard", label: "Dashboard", href: "/dashboard", icon: <LayoutDashboard {...icon} /> }, inbox, profile];
}

type Props = {
  tabs: TabItem[];
  /** The shown tab, or null on a pushed screen. */
  active: string | null;
  /** Fractional index of the shown tab: the indicator slides with a swipe. */
  progress: MotionValue<number>;
  onSelect: (id: string) => void;
  /** Draw in the flow, on every screen size, instead of fixed to the bottom of phones. For /design. */
  inline?: boolean;
  /** Accessible name of the navigation. Default "Main"; only /design needs to tell several bars apart. */
  label?: string;
};

/** Mobile bottom bar (DESIGN.md §3, TabBar.dc.html): icons with labels, translucent material, a selection indicator that follows swipes. */
export function TabBar({ tabs, active, progress, onSelect, inline, label = "Main" }: Props) {
  const x = useTransform(progress, (v) => `${v * 100}%`);
  return (
    <nav aria-label={label} className={cx("material border-t border-separator", inline ? "relative" : "fixed inset-x-0 bottom-0 z-30 pb-[env(safe-area-inset-bottom)] lg:hidden")}>
      <div className="relative grid pt-2" style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr))` }}>
        {active && (
          <motion.span aria-hidden className="pointer-events-none absolute top-0 flex justify-center" style={{ width: `${100 / tabs.length}%`, x }}>
            <span className="h-0.5 w-8 rounded-full bg-text" />
          </motion.span>
        )}
        {tabs.map((t) => (
          <a
            key={t.id}
            href={t.href}
            aria-current={t.id === active ? "page" : undefined}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
              e.preventDefault();
              onSelect(t.id);
            }}
            className={cx("relative flex min-h-11 flex-col items-center justify-start gap-1 pb-2 t-caption active:opacity-80", t.id === active ? "font-semibold text-text" : "text-text-subtle")}
          >
            <span className="relative">
              {t.icon}
              {t.dot && <span aria-hidden className="absolute -right-0.5 -top-0.5 h-2.5 w-2.5 rounded-full bg-live ring-2 ring-bg" />}
            </span>
            {t.label}
          </a>
        ))}
      </div>
    </nav>
  );
}
