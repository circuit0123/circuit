"use client";

import { CircuitsIcon, cx, type TabItem } from "@circuit/ui";

/** Icons from PMNav.dc.html, keyed by tab id. A tab the design has no icon for (Circuits, Dashboard) keeps the one the shared preset gives it. */
const ICONS: Record<string, React.ReactNode> = {
  home: <path d="M4 10.5L12 4l8 6.5V20h-5v-6H9v6H4z" />,
  discover: (<><circle cx="12" cy="12" r="8.5" /><path d="M15.5 8.5l-2 5-5 2 2-5z" /></>),
  inbox: <path d="M4 5h16v11H9l-5 4z" />,
  profile: (<><circle cx="12" cy="8.5" r="4" /><path d="M4.5 20c1.2-3.6 4-5.5 7.5-5.5s6.3 1.9 7.5 5.5" /></>),
};

function TabIcon({ t }: { t: TabItem }) {
  if (t.id === "circuits") return <CircuitsIcon size={20} strokeWidth={2} />;
  const d = ICONS[t.id];
  if (!d) return <span className="flex h-5 w-5 items-center justify-center [&>svg]:h-5 [&>svg]:w-5">{t.icon}</span>;
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" aria-hidden>{d}</svg>
  );
}

type Props = {
  tabs: TabItem[];
  active: string | null;
  onSelect: (id: string) => void;
  /** Present when the member can write a build log: draws the + button after the second tab. */
  onCompose?: () => void;
};

/** v2 bottom bar (PMNav.dc.html): a floating card, 12px in from the edges, the active tab in a tinted pill, the + in the middle. Phones only; the desktop rail stays. */
export function NavV2({ tabs, active, onSelect, onCompose }: Props) {
  const cols = tabs.length + (onCompose ? 1 : 0);
  const items: (TabItem | "compose")[] = [...tabs];
  if (onCompose) items.splice(Math.min(2, tabs.length), 0, "compose");
  return (
    <nav
      aria-label="Main"
      className="fixed inset-x-3 z-30 mx-auto grid h-16 max-w-[366px] items-center rounded-[20px] border border-c-border bg-c-card px-1.5 text-[10px] lg:hidden"
      style={{ bottom: "calc(12px + env(safe-area-inset-bottom))", gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, boxShadow: "0 -12px 30px rgba(10,10,12,0.8)" }}
    >
      {items.map((t) =>
        t === "compose" ? (
          <button key="compose" type="button" aria-label="New build log" onClick={onCompose} className="flex justify-center">
            <span className="flex h-[46px] w-[46px] items-center justify-center rounded-[14px] bg-c-bright text-c-bg">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" aria-hidden><path d="M12 5v14M5 12h14" /></svg>
            </span>
          </button>
        ) : (
          <a
            key={t.id}
            href={t.href}
            aria-current={t.id === active ? "page" : undefined}
            aria-label={t.dot ? `${t.label}, unread messages` : undefined}
            onClick={(e) => {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
              e.preventDefault();
              onSelect(t.id);
            }}
            className={cx("relative mx-[3px] flex h-[50px] flex-col items-center justify-center gap-[3px] rounded-[14px] font-semibold", t.id === active ? "bg-c-bright-bg text-c-bright" : "text-c-muted")}
          >
            <TabIcon t={t} />
            {t.label}
            {t.dot && <span aria-hidden className="absolute right-4 top-1.5 h-[7px] w-[7px] rounded-full bg-c-bright" />}
          </a>
        ),
      )}
    </nav>
  );
}
