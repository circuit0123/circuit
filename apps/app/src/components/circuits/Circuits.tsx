"use client";

import { Button, CircuitRing, EmptyState, ErrorState, MiniRing, Screen, Section, Sheet, Skeleton, cx, useToast } from "@circuit/ui";
import { Star } from "lucide-react";
import { useState } from "react";
import { capabilityPhrase, loadFailed, useCircuits, useMarkDone, useMe, useRateHandover, useRespondCircuit, type CircuitView } from "@/data";

/**
 * Circuits (DESIGN.md §4 "Circuits (signature screen)", Circuits.dc.html). What the member is doing here: answer this week's proposal,
 * then do their part. The most important element is the ring: three people, each segment lit as its person says yes, closing with the
 * signature moment when all three are in.
 */
export function Circuits() {
  const me = useMe().data;
  const list = useCircuits();
  const empty = !list.isPending && !list.isError && list.current.length === 0;
  // One primary button per screen: only the first card with something to do gets it.
  const firstAction = list.current.find((c) => c.step === "answer")?.id ?? null;

  return (
    <Screen title="Circuits">
      {list.isPending && <Section label="Loading circuits"><CardSkeleton /></Section>}
      {list.isError && <Section><ErrorState text={loadFailed("circuits")} onRetry={() => list.refetch()} /></Section>}
      {empty && (
        <Section>
          <EmptyState
            text={me?.isMinor ? "Exchange circuits are for members 18 and over. Discover has roles and people near you." : "Add what you need and what you can offer to join this week's round."}
          />
        </Section>
      )}
      {list.current.map((c) => (
        <Section key={c.id} label={c.status === "proposed" ? "This week's circuit" : `Circuit with ${c.youHelp.name}`}>
          <CircuitCard c={c} primary={c.id === firstAction} closing={list.celebrating.includes(c.id)} onClosed={() => list.celebrated(c.id)} />
        </Section>
      ))}
      {list.history.length > 0 && (
        <Section title="Completed">
          <div className="flex flex-wrap items-center gap-4">
            {list.history.map((h) => <MiniRing key={h.id} label={h.label} />)}
            <span className="t-subhead text-text-muted">{list.history.length === 1 ? "1 circuit closed" : `${list.history.length} circuits closed`}</span>
          </div>
        </Section>
      )}
    </Screen>
  );
}

function CircuitCard({ c, primary, closing, onClosed }: { c: CircuitView; primary: boolean; closing: boolean; onClosed: () => void }) {
  const respond = useRespondCircuit();
  const toast = useToast();
  const [declining, setDeclining] = useState(false);
  const [marking, setMarking] = useState(false);
  const failed = () => toast({ text: "Couldn't send that. Check your connection and try again.", tone: "error" });

  return (
    <article className="rounded-card bg-surface p-5 lg:p-6" data-circuit-id={c.id}>
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="t-headline">{c.title}</h2>
        {c.timeLeft && <span className="num t-subhead shrink-0 text-text-muted">{c.timeLeft}</span>}
      </div>

      <CircuitRing className="mt-4" members={c.ring.members} centre={c.ring.centre} label={c.ring.label} closing={closing} onDone={onClosed} />

      <ul className="mt-5 flex flex-col gap-3" aria-label="Who helps whom">
        {c.lines.map((l) => (
          <li key={l.key} className={cx("t-body", !l.you && "text-text-muted")}>
            {l.giver} {l.giver === "You" ? "help" : "helps"} {l.receiver} with {l.you ? <span className="font-semibold">{capabilityPhrase(l.capability)}</span> : capabilityPhrase(l.capability)}
            {l.state && ` · ${l.state}`}
          </li>
        ))}
      </ul>

      {c.step === "answer" && (
        <div className="mt-6 flex flex-col">
          <Button
            variant={primary ? "primary" : "secondary"}
            className="w-full"
            disabled={respond.isPending}
            onClick={() => respond.mutate({ id: c.id, accept: true }, { onError: failed })}
          >
            Accept
          </Button>
          <button type="button" onClick={() => setDeclining(true)} className="mt-1 min-h-11 w-full rounded-control t-body text-text-muted active:opacity-80">Decline</button>
        </div>
      )}
      {c.status === "proposed" && c.step === "waiting" && (
        <p className="t-body mt-6 text-text-muted" role="status">You said yes. Waiting for {joinNames(c.waitingFor)}.</p>
      )}
      {c.status === "active" && (
        <p className="t-body mt-6" role="status">Circuit closed. You help {c.youHelp.name} with {capabilityPhrase(c.youHelp.capability)}. We&apos;ll check in next week.</p>
      )}
      {c.doneLeg && (
        <Button variant="secondary" className="mt-4 w-full" onClick={() => setMarking(true)}>Mark my part done</Button>
      )}
      {c.status === "active" && !c.doneLeg && c.step === "waiting" && (
        <p className="t-subhead mt-4 text-text-muted">You&apos;ve done your part. The others are finishing theirs.</p>
      )}
      {c.status === "completed" && <p className="t-body mt-6" role="status">All three of you did your part.</p>}
      {c.rateLeg && <Rate c={c} leg={c.rateLeg} />}

      <DeclineSheet open={declining} onClose={() => setDeclining(false)} c={c} />
      {c.doneLeg && <DoneSheet open={marking} onClose={() => setMarking(false)} c={c} leg={c.doneLeg} />}
    </article>
  );
}

const joinNames = (n: string[]) => (n.length <= 1 ? n.join("") : `${n.slice(0, -1).join(", ")} and ${n[n.length - 1]}`);

function DeclineSheet({ open, onClose, c }: { open: boolean; onClose: () => void; c: CircuitView }) {
  const respond = useRespondCircuit();
  const toast = useToast();
  return (
    <Sheet open={open} onClose={onClose} title="Decline this circuit?" detents={["medium"]}>
      <p className="t-body text-text-muted">One no ends it for all three of you, and they&apos;re told it won&apos;t go ahead.</p>
      <Button
        variant="destructive"
        className="mt-6 w-full"
        disabled={respond.isPending}
        onClick={() => respond.mutate({ id: c.id, accept: false }, {
          onSuccess: () => { onClose(); toast({ text: "Declined. This circuit won't go ahead." }); },
          onError: () => toast({ text: "Couldn't send that. Try again.", tone: "error" }),
        })}
      >
        Decline
      </Button>
      <Button variant="secondary" className="mt-3 w-full" onClick={onClose}>Keep it</Button>
    </Sheet>
  );
}

function DoneSheet({ open, onClose, c, leg }: { open: boolean; onClose: () => void; c: CircuitView; leg: NonNullable<CircuitView["doneLeg"]> }) {
  const done = useMarkDone();
  const toast = useToast();
  return (
    <Sheet open={open} onClose={onClose} title={`Done helping ${leg.receiver}?`} detents={["medium"]}>
      <p className="t-body text-text-muted">{leg.receiver} will be asked how your help with {capabilityPhrase(leg.capability)} went.</p>
      <Button
        variant="primary"
        className="mt-6 w-full"
        disabled={done.isPending}
        onClick={() => done.mutate({ id: c.id, leg: leg.id }, {
          onSuccess: () => { onClose(); toast({ text: "Marked done. Thank you." }); },
          onError: () => toast({ text: "Couldn't send that. Try again.", tone: "error" }),
        })}
      >
        Yes, it&apos;s done
      </Button>
      <Button variant="secondary" className="mt-3 w-full" onClick={onClose}>Not yet</Button>
    </Sheet>
  );
}

function Rate({ c, leg }: { c: CircuitView; leg: NonNullable<CircuitView["rateLeg"]> }) {
  const rate = useRateHandover();
  const toast = useToast();
  const [picked, setPicked] = useState<number | null>(null);
  const label = `How was ${leg.giver}'s help with ${capabilityPhrase(leg.capability)}?`;
  return (
    <div className="mt-6">
      <p className="t-body" id={`rate-${c.id}`}>{label}</p>
      <div role="radiogroup" aria-labelledby={`rate-${c.id}`} className="mt-2 flex gap-1" data-no-swipe>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={picked === n}
            aria-label={`${n} out of 5`}
            disabled={rate.isPending}
            onClick={() => {
              setPicked(n);
              rate.mutate({ id: c.id, leg: leg.id, rating: n }, {
                onSuccess: () => toast({ text: "Thanks for rating." }),
                onError: () => { setPicked(null); toast({ text: "Couldn't send that. Try again.", tone: "error" }); },
              });
            }}
            className="flex h-11 w-11 items-center justify-center rounded-full text-text active:scale-[0.97]"
          >
            <Star size={24} strokeWidth={1.75} aria-hidden fill={picked !== null && n <= picked ? "currentColor" : "none"} />
          </button>
        ))}
      </div>
    </div>
  );
}

function CardSkeleton() {
  return (
    <div className="rounded-card bg-surface p-5" aria-hidden>
      <Skeleton className="h-5 w-40" />
      <Skeleton round className="mx-auto mt-6 h-[176px] w-[176px]" />
      <Skeleton className="mt-6 h-4 w-3/4" />
      <Skeleton className="mt-3 h-4 w-2/3" />
      <Skeleton className="mt-3 h-4 w-2/3" />
    </div>
  );
}
