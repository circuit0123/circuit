"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { firstName, type RingMember } from "@circuit/ui";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Schemas } from "@circuit/api-client";
import { api, unwrap } from "./client";
import { useKey } from "./keys";
import { useChannel } from "./realtime";

type Out = Schemas["CircuitOut"];
type Page = Schemas["Page_CircuitOut_"];

export type CircuitStep = "answer" | "waiting" | "mark_done" | "rate" | "none";

/** One who-helps-whom line. `you` marks the viewer's own handover (it carries the capability in semibold). */
export type CircuitLine = { key: number; giver: string; receiver: string; capability: string; you: boolean; state: string | null };

/** A proposed or active circuit, ready to draw (DESIGN.md §4 Circuits, Circuits.dc.html). */
export type CircuitView = {
  id: number;
  /** `completed` only while the viewer still has a handover to rate. */
  status: "proposed" | "active" | "completed";
  title: string;
  /** "2d 14h left" while proposed; null once it is running. */
  timeLeft: string | null;
  ring: { members: [RingMember, RingMember, RingMember]; centre: string; label: string };
  lines: CircuitLine[];
  step: CircuitStep;
  /** All three said yes: the ring is closed. */
  closed: boolean;
  /** "You help Priya with fundraising." */
  youHelp: { name: string; capability: string };
  /** Who hasn't answered yet (first names), for "Waiting for Arjun". */
  waitingFor: string[];
  /** The handover the viewer gives, while it can be marked done. */
  doneLeg: { id: number; receiver: string; capability: string } | null;
  /** The handover the viewer received, once it is done and not rated. */
  rateLeg: { id: number; giver: string; capability: string } | null;
};

export type CircuitHistoryItem = { id: number; label: string };

/** Names that stay capitalised inside a sentence ("You help Asha with React"). */
const PROPER = /^(React|Django|Python|Flutter|Figma|Go|Rust|Java|Kotlin|Swift|AWS|SQL|Postgre|Next|Node|C\b)/;
/** A capability as it reads mid-sentence: "Fundraising" → "fundraising", but "React" stays "React". */
export const capabilityPhrase = (c: string) => (PROPER.test(c) || /^[A-Z]{2}/.test(c) ? c : c.charAt(0).toLowerCase() + c.slice(1));

/** "2d 14h left", "5h left", "40m left". */
export function timeLeftText(seconds: number | null): string | null {
  if (seconds == null) return null;
  const m = Math.max(0, Math.floor(seconds / 60));
  const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60);
  if (d > 0) return `${d}d ${h}h left`;
  if (h > 0) return `${h}h left`;
  return `${Math.max(1, m)}m left`;
}

const join = (names: string[]) => (names.length <= 1 ? names.join("") : `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}`);

export function toCircuitView(c: Out): CircuitView {
  const consent = new Map(c.members.map((m) => [m.person.id, m.consent]));
  const meId = c.members.find((m) => m.is_me)?.person.id ?? c.legs.find((l) => l.i_give)?.giver.id ?? 0;
  // Ring order: start with me, then whoever I help, then whoever they help.
  const legs: Out["legs"] = [];
  let at = meId;
  for (let i = 0; i < 3; i++) {
    const leg = c.legs.find((l) => l.giver.id === at);
    if (!leg) break;
    legs.push(leg);
    at = leg.receiver.id;
  }
  const ordered = legs.length === 3 ? legs : c.legs;
  const label = (p: Schemas["PersonOut"]) => (p.id === meId ? "You" : firstName(p.display_name));
  const members = ordered.map((l) => ({ id: l.giver.id, name: l.giver.display_name, label: label(l.giver), lit: consent.get(l.giver.id) === "accepted" })) as CircuitView["ring"]["members"];
  const accepted = members.filter((m) => m.lit).length;
  const closed = accepted === 3;
  const others = members.slice(1);
  const pending = members.filter((m) => !m.lit).map((m) => (m.id === meId ? "you" : m.label));
  const active = c.status === "active";
  const completed = c.status === "completed";

  const ringLabel = closed
    ? `Circuit closed: ${join(others.map((m) => m.label))} and you all said yes`
    : accepted === 0 ? "Nobody has answered yet"
    : `${join(members.filter((m) => m.lit).map((m) => (m.id === meId ? "You" : m.label)))} accepted, waiting for ${join(pending)}`;

  const lines: CircuitLine[] = ordered.map((l) => {
    const you = l.giver.id === meId;
    let state: string | null = null;
    if (active || completed) state = l.fulfilled ? "done" : null;
    else if (!you) state = l.consent === "accepted" ? "accepted" : l.consent === "declined" ? "declined" : null;
    return { key: l.id, giver: label(l.giver), receiver: l.receiver.id === meId ? "you" : firstName(l.receiver.display_name), capability: l.capability, you, state };
  });

  const done = c.legs.find((l) => l.can_mark_done);
  const rate = c.legs.find((l) => l.can_rate);
  return {
    id: c.id,
    status: completed ? "completed" : active ? "active" : "proposed",
    title: completed ? "Circuit complete" : active || closed ? "Circuit closed" : "Proposed for you",
    timeLeft: c.status === "proposed" ? timeLeftText(c.time_left_seconds) : null,
    ring: { members, centre: `${accepted} of 3 in`, label: ringLabel },
    lines,
    step: c.next_step as CircuitStep,
    closed,
    youHelp: { name: firstName(c.you_help.person.display_name), capability: c.you_help.capability },
    waitingFor: members.filter((m) => !m.lit && m.id !== meId).map((m) => m.label),
    doneLeg: done ? { id: done.id, receiver: firstName(done.receiver.display_name), capability: done.capability } : null,
    rateLeg: rate ? { id: rate.id, giver: firstName(rate.giver.display_name), capability: rate.capability } : null,
  };
}

const MONTH = new Intl.DateTimeFormat("en-IN", { timeZone: "Asia/Kolkata", month: "long" });
const SEEN_KEY = (id: number) => `circuit.closed.${id}`;
const seenClosing = (id: number) => { try { return localStorage.getItem(SEEN_KEY(id)) === "1"; } catch { return false; } };
const rememberClosing = (id: number) => { try { localStorage.setItem(SEEN_KEY(id), "1"); } catch { /* plays again next time: harmless */ } };

/**
 * The Circuits tab: proposed and active circuits as cards, completed ones as history. Each card listens to its own Realtime channel
 * (`circuit:<id>`, event `status`) and refetches when someone answers, so their segment lights up live.
 *
 * `celebrating` holds the circuits whose ring just closed while this screen was open (a live answer, or the viewer's own Accept) and
 * whose closing moment hasn't played yet; it plays once per circuit (remembered on this device). A ring that was already closed when
 * the screen first loaded doesn't replay.
 */
export function useCircuits() {
  const { key, enabled } = useKey("circuits");
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: key,
    enabled,
    refetchInterval: 60_000, // keeps "time left" honest; Realtime brings answers at once
    queryFn: () => unwrap(api.GET("/api/circuits", { params: { query: { limit: 20 } } })),
  });

  const items = q.data?.items ?? [];
  // A completed circuit stays a card until the viewer has rated what they received; then it joins the history.
  const rating = (c: Out) => c.status === "completed" && c.next_step === "rate";
  const current = items.filter((c) => c.status === "proposed" || c.status === "active" || rating(c)).map(toCircuitView);
  const history: CircuitHistoryItem[] = items.filter((c) => c.status === "completed" && !rating(c)).map((c) => ({ id: c.id, label: `Completed circuit, ${MONTH.format(new Date(c.created_at))}` }));

  // Live: one channel per circuit still in play (there is normally one a week).
  const live = current.filter((c) => c.status === "proposed").map((c) => c.id);
  useChannel(live[0] ? `circuit:${live[0]}` : null, "status", () => qc.invalidateQueries({ queryKey: key }));
  useChannel(live[1] ? `circuit:${live[1]}` : null, "status", () => qc.invalidateQueries({ queryKey: key }));

  // The closing moment: a ring seen open that is now closed.
  const was = useRef(new Map<number, boolean>());
  const [celebrating, setCelebrating] = useState<number[]>([]);
  const closedIds = current.filter((c) => c.closed).map((c) => c.id).join(",");
  useEffect(() => {
    const next: number[] = [];
    for (const c of current) {
      const before = was.current.get(c.id);
      if (before === false && c.closed && !seenClosing(c.id)) next.push(c.id);
      was.current.set(c.id, c.closed);
    }
    if (next.length) setCelebrating((s) => [...s, ...next.filter((id) => !s.includes(id))]); // eslint-disable-line react-hooks/set-state-in-effect
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [closedIds, q.dataUpdatedAt]);
  const celebrated = useCallback((id: number) => {
    rememberClosing(id);
    setCelebrating((s) => s.filter((x) => x !== id));
  }, [setCelebrating]);

  return { current, history, isPending: q.isPending, isError: q.isError, refetch: q.refetch, celebrating, celebrated };
}

/** Puts one circuit from a mutation's answer into the list, so the card changes without waiting for a refetch. */
function useReplace() {
  const qc = useQueryClient();
  const { key } = useKey("circuits");
  return (c: Out) => qc.setQueryData<Page>(key, (old) => old && { ...old, items: old.items.map((x) => (x.id === c.id ? c : x)) });
}

/** Accept or Decline. One no ends the circuit for everyone. */
export function useRespondCircuit() {
  const replace = useReplace();
  return useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) => unwrap(api.POST("/api/circuits/{circuit_id}/respond", { params: { path: { circuit_id: id } }, body: { accept } })),
    onSuccess: replace,
  });
}

/** "I've done my part." */
export function useMarkDone() {
  const replace = useReplace();
  return useMutation({
    mutationFn: ({ id, leg }: { id: number; leg: number }) => unwrap(api.POST("/api/circuits/{circuit_id}/legs/{leg_id}/done", { params: { path: { circuit_id: id, leg_id: leg } } })),
    onSuccess: replace,
  });
}

/** Rates what the viewer received, 1 to 5. The first rating stands. */
export function useRateHandover() {
  const replace = useReplace();
  return useMutation({
    mutationFn: ({ id, leg, rating }: { id: number; leg: number; rating: number }) =>
      unwrap(api.POST("/api/circuits/{circuit_id}/legs/{leg_id}/rating", { params: { path: { circuit_id: id, leg_id: leg } }, body: { rating } })),
    onSuccess: replace,
  });
}
