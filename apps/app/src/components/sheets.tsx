"use client";

import { Button, ErrorState, SearchField, Sheet, Skeleton, cx, useToast } from "@circuit/ui";
import { useState } from "react";
import { useCapabilities } from "@/data";

export const REPORT_REASONS = ["Spam or a scam", "Harassment or hate", "Pretending to be someone else", "Something else"] as const;

/** Report something (DESIGN.md §8: within two taps): one reason, then a destructive "Send report". */
export function ReportSheet({ open, onClose, title, intro, onSend }: { open: boolean; onClose: () => void; title: string; intro: string; onSend: (reason: string) => Promise<unknown> }) {
  const toast = useToast();
  const [reason, setReason] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const close = () => { setReason(null); onClose(); };
  return (
    <Sheet open={open} onClose={close} title={title} detents={["medium", "large"]}>
      <p className="t-body text-text-muted">{intro}</p>
      <div role="radiogroup" aria-label="What's wrong?" className="mt-4 flex flex-col">
        {REPORT_REASONS.map((r) => (
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
          try { await onSend(reason); close(); toast({ text: "Thanks. We'll look at this within a day." }); }
          catch { toast({ text: "Couldn't send that. Try again.", tone: "error" }); }
          finally { setBusy(false); }
        }}
      >
        Send report
      </Button>
    </Sheet>
  );
}

/** "Are you sure?" for something that can't be undone: the destructive action, then Cancel. */
export function ConfirmSheet({ open, onClose, title, text, confirmLabel, onConfirm, busy }: {
  open: boolean; onClose: () => void; title: string; text: string; confirmLabel: string; onConfirm: () => void; busy?: boolean;
}) {
  return (
    <Sheet open={open} onClose={onClose} title={title} detents={["medium"]}>
      <p className="t-body text-text-muted">{text}</p>
      <Button variant="destructive" className="mt-6 w-full" disabled={busy} onClick={onConfirm}>{confirmLabel}</Button>
      <Button variant="secondary" className="mt-3 w-full" onClick={onClose}>Cancel</Button>
    </Sheet>
  );
}

/** Picks capabilities from the fixed list, with search. `chosen` are slugs; `limit` caps how many (tags 3, offers 5, needs 3). */
export function CapabilitySheet({ open, onClose, title, chosen, limit, onToggle }: {
  open: boolean; onClose: () => void; title: string; chosen: string[]; limit: number; onToggle: (slug: string) => void;
}) {
  const caps = useCapabilities();
  const [query, setQuery] = useState("");
  const q = query.trim().toLowerCase();
  const list = (caps.data ?? []).filter((c) => !q || c.name.toLowerCase().includes(q));
  const full = chosen.length >= limit;
  return (
    <Sheet open={open} onClose={() => { setQuery(""); onClose(); }} title={title} detent="large" detents={["large"]}>
      <SearchField aria-label="Search skills" placeholder="Search skills" value={query} onChange={(e) => setQuery(e.target.value)} />
      <p className="num t-footnote mt-3 text-text-muted" role="status">{chosen.length} of {limit}{full ? ". Remove one to add another." : ""}</p>
      {caps.isError ? (
        <ErrorState className="mt-4" text="Couldn't load the list." onRetry={() => void caps.refetch()} />
      ) : !caps.data ? (
        <div className="mt-4 flex flex-col gap-3" aria-hidden>{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
      ) : (
        <ul className="mt-2">
          {list.map((c) => {
            const on = chosen.includes(c.slug);
            return (
              <li key={c.slug}>
                <button
                  type="button"
                  aria-pressed={on}
                  disabled={!on && full}
                  onClick={() => onToggle(c.slug)}
                  className="flex min-h-14 w-full items-center justify-between border-b border-separator t-body active:opacity-80 disabled:opacity-50"
                >
                  {c.name}
                  <span aria-hidden className={cx("h-5 w-5 rounded-full border-2", on ? "border-text bg-text" : "border-text-subtle")} />
                </button>
              </li>
            );
          })}
          {list.length === 0 && <li className="t-body py-4 text-text-muted">Nothing matches that.</li>}
        </ul>
      )}
      <Button variant="primary" className="mt-6 w-full" onClick={() => { setQuery(""); onClose(); }}>Done</Button>
    </Sheet>
  );
}

/**
 * A ListRow for inside a GroupedList. GroupedList insets every row after the first by 16px (so the hairline lines up with the text) and
 * ListRow brings its own 16px, which pushes the text 32px in; this takes the row's own left padding off when it follows another row.
 * (PROGRESS.md F6 "Shared UI changes needed": fix in GroupedList, then this goes.)
 */
export const ROW_INSET = "[li+li>&]:pl-0";
