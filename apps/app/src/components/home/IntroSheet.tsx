"use client";

import { Button, Sheet, Skeleton, firstName, useToast } from "@circuit/ui";
import { createContext, useCallback, useContext, useState } from "react";
import { IntroError, useIntroCapacity, useIntroPath, useRequestIntro, type IntroFailure } from "@/data";

type Target = { id: number; name: string; /** From the Daily Drop: the swipe is recorded with the intro. */ fromDrop?: boolean };
type Ask = (target: Target, onSent?: () => void) => void;
const Ctx = createContext<Ask>(() => {});

/** Every "Intro me" opens the same confirm sheet. Returns `ask(target, onSent)`; `onSent` runs after the request went through. */
export const useAskIntro = () => useContext(Ctx);

/** One sentence per reason an intro can't be sent (DESIGN.md §9: what happened, what to do). */
export function introFailureText(f: IntroFailure, name: string): string {
  switch (f) {
    case "weekly_limit": return "You've used this week's intros. You can ask again next week.";
    case "target_full": return `${name} isn't taking more intros this week. Try again next week.`;
    case "no_path": return `You don't share a connection with ${name} yet.`;
    case "under_18": return "Introductions aren't available for under-18 accounts.";
    default: return "Couldn't send that. Check your connection and try again.";
  }
}

export function IntroProvider({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState<{ target: Target; onSent?: () => void } | null>(null);
  const ask = useCallback<Ask>((target, onSent) => setOpen({ target, onSent }), []);
  return (
    <Ctx.Provider value={ask}>
      {children}
      <IntroSheet open={open} onClose={() => setOpen(null)} />
    </Ctx.Provider>
  );
}

function IntroSheet({ open, onClose }: { open: { target: Target; onSent?: () => void } | null; onClose: () => void }) {
  const target = open?.target;
  const path = useIntroPath(target?.id ?? null);
  const send = useRequestIntro();
  const capacity = useIntroCapacity(!!target);
  const toast = useToast();
  const name = target ? firstName(target.name) : "";

  // What the sheet says. Errors from sending win over what the path said.
  const sendFailure = send.error instanceof IntroError ? send.error.failure : send.isError ? "failed" : null;
  const pathFailure: IntroFailure | null = path.isError ? (path.error instanceof IntroError ? path.error.failure : "failed") : null;
  const cap = capacity.data;
  // Used up already: say so before Send, with when the next one frees up.
  const capFailure: IntroFailure | null = cap && !cap.allowed ? "under_18" : cap && cap.left === 0 ? "weekly_limit" : null;
  const failure = sendFailure ?? pathFailure ?? capFailure;
  const blocked = failure !== null && failure !== "failed";
  const via = path.data?.via;

  const close = () => { send.reset(); onClose(); };
  const submit = () => {
    if (!target) return;
    send.mutate({ id: target.id, fromDrop: target.fromDrop }, {
      onSuccess: () => {
        const sent = open?.onSent;
        send.reset();
        onClose();
        toast({ text: "Intro requested. We'll tell you when they reply." });
        sent?.();
      },
    });
  };

  return (
    <Sheet open={!!open} onClose={close} title={target ? `Intro to ${name}` : "Intro"} detent="medium" detents={["medium"]}>
      {target && (
        <div className="flex flex-col gap-2">
          {path.isPending ? (
            <div aria-hidden><Skeleton className="h-5 w-4/5" /><Skeleton className="mt-2 h-4 w-3/5" /></div>
          ) : !pathFailure ? (
            <>
              <p className="text-[22px] font-medium leading-[1.25] tracking-[-0.012em]">
                {via ? <>{firstName(via.name)}, {via.role.toLowerCase()}, will introduce you to {name}.</> : <>You're already connected. We'll send your request straight to {name}.</>}
              </p>
              <p className="t-body text-text-muted">
                {via ? `${firstName(via.name)} is asked first, then ${name} says yes or no.` : `${name} can say yes or no.`} A request stays open for 7 days.
              </p>
            </>
          ) : null}
          {failure && <p role="alert" className="t-body mt-2 text-danger">{introFailureText(failure, name)}{failure === "weekly_limit" && cap?.nextFreesAt && !sendFailure ? ` The next one frees up on ${new Date(cap.nextFreesAt).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long", timeZone: "Asia/Kolkata" })}.` : ""}</p>}
          {!failure && cap && cap.allowed && cap.left > 0 && <p className="t-footnote text-text-muted">{cap.left === 1 ? "1 intro left this week." : `${cap.left} intros left this week.`}</p>}
          <div className="mt-6 flex flex-col">
            {!blocked && <Button variant="primary" className="w-full" disabled={path.isPending || !!pathFailure || send.isPending} onClick={submit}>{send.isPending ? "Sending" : "Send request"}</Button>}
            <button type="button" onClick={close} className="flex min-h-11 w-full items-center justify-center t-body text-text-muted active:opacity-80">{blocked ? "Close" : "Cancel"}</button>
          </div>
        </div>
      )}
    </Sheet>
  );
}
