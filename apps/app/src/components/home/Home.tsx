"use client";

import { Bell, Plus } from "lucide-react";
import { BarButton, EmptyState, Screen, Section, Skeleton, Button, useToast } from "@circuit/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { composeHref, useHome, useUnreadCount } from "@/data";
import { useDesktop } from "@/hooks/useDesktop";
import { DropSection } from "./DropSection";
import { LiveWireSection } from "./LiveWireSection";
import { Pulse } from "./Pulse";

export function NotificationsBell() {
  const unread = useUnreadCount().data ?? 0;
  return (
    <Link href="/notifications" aria-label={unread > 0 ? `Notifications, ${unread > 9 ? "9+" : unread} unread` : "Notifications"} className="relative flex h-11 w-11 items-center justify-center rounded-full active:opacity-80">
      <Bell size={24} strokeWidth={1.75} />
      {unread > 0 && <span className="absolute right-2.5 top-2.5 h-2 w-2 rounded-full bg-live ring-2 ring-bg" aria-hidden />}
    </Link>
  );
}

/** `+` in the top bar: a new build log. The composer is F6, so until then it says so instead of going nowhere. */
export function NewBuildLog() {
  const router = useRouter();
  const toast = useToast();
  return (
    <BarButton label="New build log" onClick={() => (composeHref ? router.push(composeHref) : toast({ text: "The build log composer is coming next." }))}>
      <Plus size={24} strokeWidth={1.75} />
    </BarButton>
  );
}

/**
 * Home (DESIGN.md §4): a `Today` title, then the Live wire, the Daily Drop (in the right rail on desktop when Pulse is on) and Pulse.
 * A feature that is off simply isn't here; with both off, a calm empty state.
 */
export function Home() {
  const home = useHome();
  const desktop = useDesktop();
  const router = useRouter();
  const dropHere = home.drop && (!desktop || !home.pulse);
  return (
    <Screen title="Today" left={home.pulse ? <NewBuildLog /> : undefined} right={<NotificationsBell />}>
      {!home.ready && <Section><Skeleton className="h-40" /></Section>}
      {home.ready && home.pulse && <Section className="pt-2"><LiveWireSection /></Section>}
      {home.ready && dropHere && <Section><DropSection /></Section>}
      {home.ready && home.pulse && <Pulse />}
      {home.ready && home.empty && (
        <Section>
          <EmptyState text="Nothing on Home right now. Look for people and startups near you in Discover." action={<Button variant="secondary" onClick={() => router.push("/discover")}>Go to Discover</Button>} />
        </Section>
      )}
    </Screen>
  );
}
