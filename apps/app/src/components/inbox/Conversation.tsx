"use client";

import { Avatar, BarButton, Button, ErrorState, PushScreen, Sheet, Skeleton, cx, firstName, useToast } from "@circuit/ui";
import { ArrowUp, ImagePlus, MoreHorizontal } from "lucide-react";
import { notFound, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  conversationHref, imageProblem, loadFailed, useConversation, useDraftConversation, useFindConversation, type Bubble, type BubbleDay,
} from "@/data";

const goBack = (router: ReturnType<typeof useRouter>) => () => (window.history.length > 1 ? router.back() : router.push("/inbox"));

/**
 * A conversation (DESIGN.md §4 Inbox, Chat.dc.html). What the member is doing: talking to one person. The most important element is
 * the thread; the one primary control is Send. Own messages are in `primary`, theirs on `surface-2`. Report and Block sit in the
 * header menu, each behind a confirm sheet. A request someone sent you waits for Accept before you can reply.
 */
export function ConversationScreen({ id }: { id: number }) {
  const router = useRouter();
  const c = useConversation(id);
  const toast = useToast();
  const [sheet, setSheet] = useState<null | "menu" | "report" | "block">(null);
  if (!Number.isFinite(id) || c.notFound) notFound();
  const name = c.head?.other.name ?? "";
  const first = name ? firstName(name) : "";

  useScrollToEnd(c.lastKey);

  const footer = !c.head ? null
    : c.head.request === "received" ? (
      <div>
        <p className="t-subhead mb-3 text-text-muted">{first} isn&apos;t one of your connections. Accept to reply.</p>
        <Button variant="primary" className="w-full" disabled={c.accept.isPending} onClick={() => c.accept.mutate(undefined, { onError: () => toast({ text: "Couldn't accept. Try again.", tone: "error" }) })}>Accept</Button>
        {c.canDecline && (
          <Button
            variant="secondary"
            className="mt-3 w-full"
            disabled={c.decline.isPending}
            onClick={() => c.decline.mutate(undefined, { onSuccess: () => { router.replace("/inbox"); toast({ text: "Request declined." }); }, onError: () => toast({ text: "Couldn't decline. Try again.", tone: "error" }) })}
          >
            Decline
          </Button>
        )}
      </div>
    )
    : c.canSend ? <Composer onSend={(text, file) => c.send(text, file)} />
    : <p className="t-subhead text-text-muted" role="status">Waiting for {first} to accept. You can write more once they reply.</p>;

  return (
    <PushScreen
      title={name}
      backLabel="Inbox"
      onBack={goBack(router)}
      bleed
      right={c.head && <BarButton label="Report or block" onClick={() => setSheet("menu")}><MoreHorizontal size={22} strokeWidth={1.75} /></BarButton>}
      footer={footer}
    >
      {c.isPending && <ThreadSkeleton />}
      {c.isError && !c.notFound && <div className="px-4 lg:px-0"><ErrorState text={loadFailed("this conversation")} onRetry={c.refetch} /></div>}
      {c.head && (
        // A short thread sits at the bottom, just above the composer (Chat.dc.html), with the person right above the first message.
        <div className="flex min-h-[calc(100dvh-220px)] flex-col justify-end">
          <PersonLine name={c.head.other.name} id={c.head.other.id} line={c.head.other.line} />
          {c.hasOlder && (
            <div className="mt-4 px-4 lg:px-0">
              <Button variant="text" className="w-full text-text-muted" disabled={c.isLoadingOlder} onClick={c.loadOlder}>Show earlier messages</Button>
            </div>
          )}
          <Thread days={c.days} other={first} onRetry={c.retry} />
        </div>
      )}
      <ConversationSheets
        sheet={sheet}
        setSheet={setSheet}
        first={first}
        onReport={(reason) => c.report(reason)}
        onBlock={() => c.block.mutateAsync()}
        onBlocked={() => { router.replace("/inbox"); toast({ text: `Blocked ${first}.` }); }}
      />
    </PushScreen>
  );
}

/** A new conversation with someone (from "New message" or a Live wire "Reply"). The first send starts it, then the screen becomes it. */
export function DraftConversationScreen({ memberId }: { memberId: number }) {
  const router = useRouter();
  const existing = useFindConversation();
  const open = existing(memberId);
  useEffect(() => { if (open) router.replace(conversationHref(open)); }, [open, router]);
  const draft = useDraftConversation(memberId, (id) => router.replace(conversationHref(id)));
  const [last, setLast] = useState<{ text: string; file: File | null; preview: string | null } | null>(null);
  if (!Number.isFinite(memberId) || draft.isError) notFound();
  const p = draft.person;
  const send = (text: string, file: File | null) => {
    const item = { text: text.trim(), file, preview: file ? URL.createObjectURL(file) : null };
    setLast(item);
    draft.start.mutate({ text: item.text, file });
  };
  const bubble: Bubble | null = last && {
    key: "draft", mine: true, body: last.text, removed: false, state: draft.start.isError ? "failed" : "sending", tempId: "draft",
    image: last.preview ? { src: last.preview, width: 4, height: 3, alt: "Photo you're sending" } : null,
  };
  return (
    <PushScreen title={p?.name ?? ""} backLabel="Inbox" onBack={goBack(router)} bleed footer={p && !last ? <Composer onSend={send} /> : null}>
      {draft.isPending && <ThreadSkeleton />}
      {p && (
        <>
          <PersonLine name={p.name} id={p.id} line={p.line} />
          {!last && <p className="t-subhead mt-6 px-4 text-text-muted lg:px-0">Your first message starts the conversation. If you&apos;re not connected, it arrives as a request.</p>}
          {bubble && <Thread days={[{ day: "Today", items: [bubble] }]} other={firstName(p.name)} onRetry={() => last && draft.start.mutate({ text: last.text, file: last.file })} />}
        </>
      )}
    </PushScreen>
  );
}

function PersonLine({ id, name, line }: { id: number; name: string; line: string }) {
  return (
    <div className="flex items-center gap-4 px-4 pt-2 lg:px-0">
      <Avatar id={id} name={name} size={64} />
      <div className="min-w-0">
        <h1 className="t-headline">{name}</h1>
        {line && <p className="t-subhead text-text-muted">{line}</p>}
      </div>
    </div>
  );
}

function Thread({ days, other, onRetry }: { days: BubbleDay[]; other: string; onRetry: (tempId: string) => void }) {
  return (
    <div role="log" aria-label="Messages" aria-live="polite" className="mt-6 flex flex-col gap-2 px-4 lg:px-0">
      {days.map((d) => (
        <section key={d.day} aria-label={d.day} className="flex flex-col gap-2">
          <h2 className="t-caption my-2 self-center text-text-subtle">{d.day}</h2>
          {d.items.map((b) => <BubbleView key={b.key} b={b} other={other} onRetry={onRetry} />)}
        </section>
      ))}
    </div>
  );
}

function BubbleView({ b, other, onRetry }: { b: Bubble; other: string; onRetry: (tempId: string) => void }) {
  const who = b.mine ? "You" : other;
  return (
    <div className={cx("flex flex-col gap-1", b.mine ? "items-end" : "items-start")} data-mine={b.mine ? "" : undefined} data-state={b.state}>
      {b.image && (
        // eslint-disable-next-line @next/next/no-img-element -- signed Supabase Storage URLs (or a local preview while sending); next/image is not used in the app
        <img
          src={b.image.src}
          alt={b.image.alt}
          width={b.image.width}
          height={b.image.height}
          className={cx("h-auto w-[min(75%,280px)] rounded-[18px] bg-surface-2 object-cover", b.state !== "sent" && "opacity-70")}
          style={{ aspectRatio: `${b.image.width} / ${b.image.height}` }}
        />
      )}
      {b.removed && <p className="t-subhead rounded-[18px] border border-separator px-3.5 py-2 text-text-subtle">Message removed</p>}
      {b.body && (
        <p
          data-bubble
          className={cx(
            "max-w-[75%] whitespace-pre-wrap break-words rounded-[18px] px-3.5 py-2.5 t-body leading-[1.35]",
            b.mine ? "bg-primary text-on-primary" : "bg-surface-2 text-text",
            b.state !== "sent" && "opacity-70",
          )}
        >
          <span className="sr-only">{who}: </span>{b.body}
        </p>
      )}
      {b.state === "sending" && <span className="t-caption text-text-subtle">Sending</span>}
      {b.state === "failed" && b.tempId && (
        <button type="button" onClick={() => onRetry(b.tempId!)} className="t-footnote -my-2 min-h-11 font-semibold text-danger active:opacity-80">Not sent. Retry</button>
      )}
    </div>
  );
}

function Composer({ onSend }: { onSend: (text: string, file: File | null) => void }) {
  const [text, setText] = useState("");
  const file = useRef<HTMLInputElement>(null);
  const toast = useToast();
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    onSend(text, null);
    setText("");
  };
  return (
    <form onSubmit={submit} className="flex items-center gap-2" aria-label="Write a message">
      <button type="button" aria-label="Share an image" onClick={() => file.current?.click()} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-text active:opacity-80">
        <ImagePlus size={22} strokeWidth={1.75} aria-hidden />
      </button>
      <input
        ref={file}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        tabIndex={-1}
        aria-hidden
        onChange={(e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          const problem = imageProblem(f);
          if (problem) { toast({ text: problem === "size" ? "That image is over 5 MB. Choose a smaller one." : "Send a JPEG, PNG or WebP image.", tone: "error" }); return; }
          onSend(text, f);
          setText("");
        }}
      />
      <label className="flex h-11 min-w-0 flex-1 items-center rounded-full bg-surface-2 px-4 focus-within:ring-2 focus-within:ring-live">
        <span className="sr-only">Message</span>
        <input value={text} onChange={(e) => setText(e.target.value)} maxLength={2000} placeholder="Message" className="t-body min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text-subtle" />
      </label>
      <button type="submit" aria-label="Send" disabled={!text.trim()} className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-primary text-on-primary transition-transform active:scale-[0.97] disabled:opacity-50">
        <ArrowUp size={20} strokeWidth={2.2} aria-hidden />
      </button>
    </form>
  );
}

const REASONS = ["Spam or a scam", "Harassment or hate", "Pretending to be someone else", "Something else"] as const;

function ConversationSheets({ sheet, setSheet, first, onReport, onBlock, onBlocked }: {
  sheet: null | "menu" | "report" | "block";
  setSheet: (s: null | "menu" | "report" | "block") => void;
  first: string;
  onReport: (reason: string) => Promise<unknown>;
  onBlock: () => Promise<unknown>;
  onBlocked: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const close = () => { setSheet(null); setReason(null); };
  return (
    <>
      <Sheet open={sheet === "menu"} onClose={close} title={first} detents={["medium"]}>
        <Button variant="secondary" className="w-full" onClick={() => setSheet("report")}>Report {first}</Button>
        <Button variant="destructive" className="mt-3 w-full" onClick={() => setSheet("block")}>Block {first}</Button>
      </Sheet>

      <Sheet open={sheet === "report"} onClose={close} title={`Report ${first}?`} detents={["medium", "large"]}>
        <p className="t-body text-text-muted">We&apos;ll look at this conversation within a day.</p>
        <div role="radiogroup" aria-label="What's wrong?" className="mt-4 flex flex-col">
          {REASONS.map((r) => (
            <button key={r} type="button" role="radio" aria-checked={reason === r} onClick={() => setReason(r)} className="flex min-h-14 items-center justify-between border-b border-separator text-left t-body">
              {r}
              <span aria-hidden className={cx("h-5 w-5 rounded-full border-2", reason === r ? "border-text bg-text" : "border-text-subtle")} />
            </button>
          ))}
        </div>
        <Button
          variant="destructive"
          className="mt-6 w-full"
          disabled={!reason || busy}
          onClick={async () => {
            if (!reason) return;
            setBusy(true);
            try { await onReport(reason); close(); toast({ text: "Thanks. We'll look at this within a day." }); }
            catch { toast({ text: "Couldn't send that. Try again.", tone: "error" }); }
            finally { setBusy(false); }
          }}
        >
          Send report
        </Button>
      </Sheet>

      <Sheet open={sheet === "block"} onClose={close} title={`Block ${first}?`} detents={["medium"]}>
        <p className="t-body text-text-muted">This conversation closes, and you won&apos;t see each other&apos;s messages, posts or intro requests any more.</p>
        <Button
          variant="destructive"
          className="mt-6 w-full"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try { await onBlock(); close(); onBlocked(); }
            catch { toast({ text: "Couldn't block. Try again.", tone: "error" }); }
            finally { setBusy(false); }
          }}
        >
          Block {first}
        </Button>
        <Button variant="secondary" className="mt-3 w-full" onClick={close}>Cancel</Button>
      </Sheet>
    </>
  );
}

/** Keeps the newest message in view: on open, on each new message and when you send. */
function useScrollToEnd(lastKey: string | null) {
  useEffect(() => {
    if (!lastKey) return;
    requestAnimationFrame(() => window.scrollTo({ top: document.documentElement.scrollHeight }));
  }, [lastKey]);
}

function ThreadSkeleton() {
  return (
    <div className="flex flex-col gap-3 px-4 pt-4 lg:px-0" aria-hidden>
      <div className="flex items-center gap-4"><Skeleton round className="h-16 w-16" /><Skeleton className="h-4 w-40" /></div>
      <Skeleton className="mt-6 h-10 w-2/3 !rounded-[18px]" />
      <Skeleton className="h-10 w-1/2 self-end !rounded-[18px]" />
      <Skeleton className="h-10 w-3/5 !rounded-[18px]" />
    </div>
  );
}
