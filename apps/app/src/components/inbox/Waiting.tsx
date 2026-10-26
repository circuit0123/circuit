"use client";

import { Avatar, Button, Section, useToast } from "@circuit/ui";
import { Star } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { introAnswerProblem, memberHref, useConnectionRequests, useIntros, useRateIntro, useRespondConnection, useRespondIntro, type IntroRow } from "@/data";

const firstName = (n: string) => n.split(" ")[0];

/**
 * What needs an answer from the viewer (DESIGN.md §4 Inbox: Requests hold intros and connection requests): people who asked to
 * connect, and intros waiting on them, either as the mutual connection who passes it on or as the person being introduced.
 * Shown above both folders so nothing is missed; draws nothing when there is nothing to answer.
 */
export function WaitingForYou() {
  const requests = useConnectionRequests();
  const received = useIntros("received");
  const brokered = useIntros("brokered");
  const intros = [...brokered.rows, ...received.rows].filter((i) => i.canRespond);
  if (requests.rows.length === 0 && intros.length === 0) return null;
  return (
    <Section title="Waiting for you">
      <ul className="flex flex-col gap-3">
        {requests.rows.map((r) => <li key={`c${r.id}`}><ConnectionCard id={r.id} from={r.from} note={r.note} /></li>)}
        {intros.map((i) => <li key={`i${i.id}`}><IntroCard i={i} /></li>)}
      </ul>
    </Section>
  );
}

function ConnectionCard({ id, from, note }: { id: number; from: { id: number; name: string; line: string }; note: string }) {
  const respond = useRespondConnection();
  const toast = useToast();
  // mutateAsync, not mutate's callbacks: the row is removed at once, so this card unmounts and those callbacks would be skipped.
  const answer = async (accept: boolean) => {
    try {
      await respond.mutateAsync({ id, accept });
      toast({ text: accept ? `You're now connected with ${firstName(from.name)}.` : "Request declined." });
    } catch { toast({ text: "Couldn't save that. Try again.", tone: "error" }); }
  };
  return (
    <div className="rounded-card bg-surface p-surface" data-testid="connection-request">
      <Link href={memberHref(from.id) ?? "/"} className="flex items-center gap-3 active:opacity-80">
        <Avatar id={from.id} name={from.name} size={40} />
        <span className="min-w-0">
          <span className="t-body block font-semibold">{from.name}</span>
          <span className="t-subhead block text-text-muted">{from.line}</span>
        </span>
      </Link>
      <p className="t-body mt-3">{note ? `“${note}”` : `${firstName(from.name)} would like to connect.`}</p>
      <Buttons disabled={respond.isPending} accept="Accept" onAnswer={answer} label={`connection request from ${from.name}`} />
    </div>
  );
}

function IntroCard({ i }: { i: IntroRow }) {
  const respond = useRespondIntro();
  const toast = useToast();
  const asBroker = i.myRole === "broker";
  const asked = i.requester.name;
  const answer = async (accept: boolean) => {
    try {
      await respond.mutateAsync({ id: i.id, accept });
      toast({ text: accept ? (asBroker ? "Passed it on." : "Intro accepted.") : "Intro declined." });
    } catch (e) { toast({ text: introAnswerProblem(e), tone: "error" }); }
  };
  return (
    <div className="rounded-card bg-surface p-surface" data-testid="intro-request">
      <p className="t-subhead text-text-muted">{asBroker ? "Intro through you" : "Intro for you"}</p>
      <p className="t-body mt-1">
        {asBroker
          ? <><Link href={memberHref(i.requester.id) ?? "/"} className="font-semibold">{asked}</Link> would like to meet <Link href={memberHref(i.target.id) ?? "/"} className="font-semibold">{i.target.name}</Link>.</>
          : <><Link href={memberHref(i.requester.id) ?? "/"} className="font-semibold">{asked}</Link> would like to meet you{i.via ? `, through ${i.via.name}` : ""}.</>}
      </p>
      {i.message && <p className="t-body mt-2 text-text-muted">“{i.message}”</p>}
      <Buttons disabled={respond.isPending} accept={asBroker ? "Pass it on" : "Accept"} onAnswer={answer} label={`intro from ${asked}`} />
    </div>
  );
}

function Buttons({ accept, onAnswer, disabled, label }: { accept: string; onAnswer: (accept: boolean) => unknown; disabled: boolean; label: string }) {
  return (
    <div className="mt-4 grid grid-cols-2 gap-3">
      <Button disabled={disabled} aria-label={`Decline ${label}`} onClick={() => onAnswer(false)}>Decline</Button>
      <Button variant="primary" disabled={disabled} aria-label={`${accept} ${label}`} onClick={() => onAnswer(true)}>{accept}</Button>
    </div>
  );
}

/**
 * The intros the viewer asked for, each with where it stands and, once accepted, a 1–5 rating (only the person who asked can rate).
 * Drawn under Chats; nothing when the viewer hasn't asked for any.
 */
export function YourIntros() {
  const sent = useIntros("sent");
  if (sent.rows.length === 0) return null;
  return (
    <Section title="Your intros">
      <ul className="flex flex-col gap-3">
        {sent.rows.map((i) => (
          <li key={i.id} className="rounded-card bg-surface p-surface" data-testid="sent-intro">
            <p className="t-body font-semibold">{i.target.name}</p>
            <p className="t-subhead text-text-muted">{i.line}</p>
            {i.status === "accepted" || i.status === "completed" ? <Rate i={i} /> : null}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Rate({ i }: { i: IntroRow }) {
  const rate = useRateIntro();
  const toast = useToast();
  const [picked, setPicked] = useState<number | null>(null);
  const shown = i.rating ?? picked;
  const id = `intro-rate-${i.id}`;
  return (
    <div className="mt-3">
      <p className="t-subhead" id={id}>{i.rating ? "You rated this intro." : `How helpful was meeting ${firstName(i.target.name)}?`}</p>
      <div role="radiogroup" aria-labelledby={id} className="mt-1 flex gap-1" data-no-swipe>
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            role="radio"
            aria-checked={shown === n}
            aria-label={`${n} out of 5`}
            disabled={rate.isPending || i.rating !== null}
            onClick={() => {
              setPicked(n);
              rate.mutate({ id: i.id, rating: n }, {
                onSuccess: () => toast({ text: "Thanks for rating." }),
                onError: (e) => { setPicked(null); toast({ text: introAnswerProblem(e), tone: "error" }); },
              });
            }}
            className="flex h-11 w-11 items-center justify-center rounded-full text-text active:scale-[0.97]"
          >
            <Star size={24} strokeWidth={1.75} aria-hidden fill={shown !== null && n <= shown ? "currentColor" : "none"} />
          </button>
        ))}
      </div>
    </div>
  );
}
