"use client";

import { Avatar, BarButton, EmptyState, ErrorState, Screen, Section, SegmentedControl, Sheet, Skeleton, cx } from "@circuit/ui";
import { SquarePen } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { conversationHref, loadFailed, newMessageHref, useConnections, useFindConversation, useInbox, type Folder, type InboxRow } from "@/data";

const FOLDERS: { id: Folder; label: string }[] = [{ id: "chats", label: "Chats" }, { id: "requests", label: "Requests" }];

/**
 * Inbox (DESIGN.md §4 Inbox, Inbox.dc.html): Chats (connections) and Requests (first messages from people you're not connected to,
 * which wait until you accept). Members under 18 get no Requests folder. Unread conversations are semibold with a dot; new messages
 * arrive live. The one action in the bar starts a new message to a connection.
 */
export function Inbox() {
  const [folder, setFolder] = useState<Folder>("chats");
  const [composing, setComposing] = useState(false);
  const chats = useInbox("chats");
  const requests = useInbox("requests");
  const shown = folder === "requests" && requests.allowed ? requests : chats;
  const current: Folder = shown === requests ? "requests" : "chats";
  const empty = !shown.isPending && !shown.isError && shown.rows.length === 0;

  return (
    <Screen title="Inbox" right={<BarButton label="New message" onClick={() => setComposing(true)}><SquarePen size={22} strokeWidth={1.75} /></BarButton>}>
      <Section label="Conversations">
        {/* On desktop the top bar isn't drawn, so the one action sits above the list. */}
        <div className="mb-4 hidden justify-end lg:flex">
          <button type="button" onClick={() => setComposing(true)} className="flex min-h-11 items-center gap-2 rounded-control px-3 t-body active:opacity-80">
            <SquarePen size={20} strokeWidth={1.75} aria-hidden />New message
          </button>
        </div>
        {requests.allowed && (
          <SegmentedControl stretch label="Inbox folders" items={FOLDERS} value={current} onChange={setFolder} className="mb-6" />
        )}
        {shown.isPending && <RowsSkeleton />}
        {shown.isError && <ErrorState text={loadFailed("your messages")} onRetry={() => shown.refetch()} />}
        {empty && (
          <EmptyState
            className="pt-6"
            text={current === "requests" ? "When someone you're not connected to writes to you, it waits here until you accept." : "No chats yet. When you connect with someone, your conversation shows up here."}
          />
        )}
        {shown.rows.length > 0 && (
          <ul aria-label={current === "requests" ? "Requests" : "Chats"} className="-mx-4 lg:mx-0">
            {shown.rows.map((r) => <li key={r.id}><Row r={r} /></li>)}
          </ul>
        )}
      </Section>
      <NewMessageSheet open={composing} onClose={() => setComposing(false)} />
    </Screen>
  );
}

function Row({ r }: { r: InboxRow }) {
  return (
    <Link href={conversationHref(r.id)} className="flex min-h-[72px] items-center gap-4 px-4 active:opacity-80 lg:px-0" data-unread={r.unread ? "" : undefined}>
      <Avatar id={r.other.id} name={r.other.name} size={44} />
      <span className="flex min-w-0 flex-1 flex-col justify-center self-stretch border-b border-separator py-3.5">
        <span className="flex items-baseline justify-between gap-2">
          <span className={cx("t-body min-w-0", r.unread ? "font-semibold" : "font-normal")}>{r.other.name}</span>
          <span className="t-subhead shrink-0 text-text-subtle">{r.time}</span>
        </span>
        <span className="mt-0.5 flex items-center justify-between gap-2">
          <span className="t-subhead line-clamp-2 min-w-0 text-text-muted">{r.waiting ? `${r.preview} · Waiting for them to accept` : r.preview}</span>
          {r.unread && <span role="img" aria-label="Unread" className="h-2.5 w-2.5 shrink-0 rounded-full bg-live" />}
        </span>
      </span>
    </Link>
  );
}

function NewMessageSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const router = useRouter();
  const people = useConnections(open);
  const existing = useFindConversation();
  const go = (memberId: number) => {
    const id = existing(memberId);
    onClose();
    router.push(id ? conversationHref(id) : newMessageHref(memberId));
  };
  return (
    <Sheet open={open} onClose={onClose} title="New message">
      {people.isPending && <RowsSkeleton />}
      {people.isError && <p role="alert" className="t-body text-text-muted">{loadFailed("your connections")}</p>}
      {people.data?.length === 0 && <p className="t-body text-text-muted">You can message your connections here. Connect with someone first, from Discover or their profile.</p>}
      {!!people.data?.length && (
        <ul aria-label="Your connections">
          {people.data.map((p) => (
            <li key={p.id}>
              <button type="button" onClick={() => go(p.id)} className="flex min-h-16 w-full items-center gap-4 text-left active:opacity-80">
                <Avatar id={p.id} name={p.name} size={40} />
                <span className="min-w-0 flex-1 border-b border-separator py-3">
                  <span className="t-body block">{p.name}</span>
                  <span className="t-subhead block text-text-muted">{p.line}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Sheet>
  );
}

function RowsSkeleton() {
  return (
    <div className="flex flex-col gap-6 pt-2" aria-hidden>
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="flex items-center gap-4"><Skeleton round className="h-12 w-12 shrink-0" /><div className="flex-1"><Skeleton className="h-4 w-1/2" /><Skeleton className="mt-2 h-3 w-4/5" /></div></div>
      ))}
    </div>
  );
}
