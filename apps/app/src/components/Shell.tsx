import { Icon, type IconName } from "@circuit/ui";
import type { ReactNode } from "react";

const NAV: { label: string; icon: IconName; current?: boolean }[] = [
  { label: "Home", icon: "home", current: true },
  { label: "Matches", icon: "users" },
  { label: "Intros", icon: "send" },
  { label: "Circuits", icon: "loop" },
];

export function Shell({ children, banner }: { children: ReactNode; banner?: string }) {
  return (
    <div className="min-h-screen md:grid md:grid-cols-[240px_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-control focus:bg-surface focus:p-3">
        Skip to content
      </a>
      <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-40 flex h-16 border-t border-rule bg-surface md:static md:h-auto md:flex-col md:gap-1 md:border-r md:border-t-0 md:p-4">
        <span className="mb-4 hidden px-3 pt-2 font-display text-xl font-extrabold md:block">Circuit</span>
        {NAV.map((n) => (
          <a
            key={n.label}
            href="#"
            aria-current={n.current ? "page" : undefined}
            className={`flex flex-1 flex-col items-center justify-center gap-0.5 text-sm font-semibold md:min-h-11 md:flex-none md:flex-row md:justify-start md:gap-3 md:rounded-control md:px-3 md:text-base ${n.current ? "text-line md:bg-line-wash" : "text-ink-soft"}`}
          >
            <Icon name={n.icon} />
            {n.label}
          </a>
        ))}
      </nav>
      <div className="min-w-0 pb-20 md:pb-0">
        {banner && (
          <aside aria-label="Environment" className="bg-ink px-4 py-2 text-center text-sm font-semibold text-white">{banner}</aside>
        )}
        <main id="main" className="mx-auto max-w-[880px] px-4 py-6 md:px-8 md:py-10">{children}</main>
      </div>
    </div>
  );
}
