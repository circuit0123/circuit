"use client";

import { Avatar, Button, EmptyState, PushScreen, Skeleton } from "@circuit/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loadFailed, useMarkRead, useNotifications, type NotificationRow } from "@/data";

/** Notifications (Notifications.dc.html, DESIGN.md §4): grouped by day, an unread dot, a tap opens what it is about. */
export function Notifications() {
  const router = useRouter();
  const list = useNotifications();
  const read = useMarkRead();
  const back = () => (window.history.length > 1 ? router.back() : router.push("/"));
  const empty = !list.isPending && !list.isError && list.groups.length === 0;

  return (
    <PushScreen title="Notifications" largeTitle backLabel="Today" onBack={back} className="px-0">
      {list.isPending && <RowsSkeleton />}
      {list.isError && (
        <div className="px-4">
          <p role="alert" className="t-body text-danger">{loadFailed("notifications")}</p>
          <Button className="mt-4" onClick={() => list.refetch()}>Try again</Button>
        </div>
      )}
      {empty && <EmptyState className="px-4 pt-8" text="Nothing new. We'll tell you when someone wants to meet you or replies." />}
      {list.groups.map((g) => (
        <section key={g.day} aria-label={g.day} className="mt-8 first:mt-5">
          <h2 className="t-headline mb-1 px-4">{g.day}</h2>
          <ul>
            {g.items.map((n) => (
              <li key={n.id}><Row n={n} onOpen={() => { if (n.unread) read.mutate(n.id); }} /></li>
            ))}
          </ul>
        </section>
      ))}
      {list.hasMore && (
        <div className="px-4 pt-6">
          <Button variant="secondary" className="w-full" disabled={list.isLoadingMore} onClick={list.loadMore}>Show earlier</Button>
        </div>
      )}
    </PushScreen>
  );
}

function Row({ n, onOpen }: { n: NotificationRow; onOpen: () => void }) {
  return (
    <Link href={n.href} onClick={onOpen} className="flex min-h-14 items-start gap-4 px-4 py-3.5 active:opacity-80">
      <Avatar id={n.actor?.id ?? `n${n.id}`} name={n.actor?.name ?? "Circuit"} size={40} />
      <span className="min-w-0 flex-1">
        <span className="t-body block leading-[1.35]">{n.text}</span>
        <span className="t-subhead mt-0.5 block text-text-subtle">{n.time}</span>
      </span>
      {n.unread && <span role="img" aria-label="Unread" className="mt-2 h-2.5 w-2.5 shrink-0 rounded-full bg-live" />}
    </Link>
  );
}

function RowsSkeleton() {
  return (
    <div className="mt-6 flex flex-col gap-6 px-4" aria-hidden>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex gap-4"><Skeleton round className="h-10 w-10 shrink-0" /><div className="flex-1"><Skeleton className="h-4 w-4/5" /><Skeleton className="mt-2 h-3 w-12" /></div></div>
      ))}
    </div>
  );
}
