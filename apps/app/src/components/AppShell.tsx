"use client";

import { Bell, CircleDot, Compass, Home, MessageCircle, Plus, UserRound } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Button, cx } from "@circuit/ui";
import { useUnreadCount } from "@/hooks/home";
import { DevBar } from "./DevBar";

const NAV = [
  { href: "/", label: "Home", Icon: Home },
  { href: "/discover", label: "Discover", Icon: Compass },
  { href: "/circuits", label: "Circuits", Icon: CircleDot },
  { href: "/inbox", label: "Inbox", Icon: MessageCircle },
  { href: "/profile", label: "Profile", Icon: UserRound },
] as const;

const active = (path: string, href: string) => (href === "/" ? path === "/" : path.startsWith(href));

export function AppShell({ children, rail }: { children: React.ReactNode; rail?: React.ReactNode }) {
  const path = usePathname();
  const unread = useUnreadCount().data?.value ?? 0;
  const bell = (
    <Link href="/notifications" aria-label={unread > 0 ? `Notifications, ${unread > 9 ? "9+" : unread} unread` : "Notifications"} className="relative flex h-11 w-11 items-center justify-center rounded-full">
      <Bell size={24} strokeWidth={1.75} />
      {unread > 0 && <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full bg-accent ring-2 ring-bg" aria-hidden />}
    </Link>
  );
  return (
    <div className="min-h-dvh">
      <DevBar />
      {/* Desktop left rail */}
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-60 flex-col gap-2 border-r border-border px-4 py-6 lg:flex" style={{ top: "var(--dev-bar, 0px)" }}>
        <Link href="/" className="t-title mb-6 px-3">Circuit</Link>
        <nav aria-label="Main" className="flex flex-col gap-1">
          {NAV.map(({ href, label, Icon }) => (
            <Link key={href} href={href} aria-current={active(path, href) ? "page" : undefined} className={cx("flex min-h-12 items-center gap-4 rounded-full px-3 t-body", active(path, href) ? "font-semibold text-text" : "text-text-muted")}>
              <Icon size={24} strokeWidth={1.75} aria-hidden />
              {label}
            </Link>
          ))}
        </nav>
        <Button className="mt-4" icon={<Plus size={20} strokeWidth={1.75} />}>New build log</Button>
        <div className="mt-auto">{bell}</div>
      </aside>

      <div className="lg:pl-60">
        {/* Mobile top bar */}
        <header className="sticky top-0 z-20 grid h-14 grid-cols-[1fr_auto_1fr] items-center border-b border-border bg-bg px-2 lg:hidden" style={{ top: "var(--dev-bar, 0px)" }}>
          <button aria-label="New build log" className="flex h-11 w-11 items-center justify-center rounded-full"><Plus size={24} strokeWidth={1.75} /></button>
          <Link href="/" className="t-headline">Circuit</Link>
          <div className="flex justify-end">{bell}</div>
        </header>

        <div className="mx-auto flex w-full max-w-[1000px] justify-center gap-10 lg:px-6">
          <main className="w-full min-w-0 pb-24 lg:max-w-[600px] lg:pb-12">{children}</main>
          {rail && <aside aria-label="For you" className="sticky hidden w-80 shrink-0 self-start py-6 lg:block" style={{ top: "var(--dev-bar, 0px)" }}>{rail}</aside>}
        </div>
      </div>

      {/* Mobile bottom bar */}
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-20 grid grid-cols-5 border-t border-border bg-bg pb-[env(safe-area-inset-bottom)] lg:hidden">
        {NAV.map(({ href, label, Icon }) => (
          <Link key={href} href={href} aria-current={active(path, href) ? "page" : undefined} className={cx("flex min-h-14 flex-col items-center justify-center gap-0.5 t-micro", active(path, href) ? "font-semibold text-text" : "text-text-muted")}>
            <Icon size={24} strokeWidth={1.75} aria-hidden />
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
