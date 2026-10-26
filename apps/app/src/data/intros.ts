"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { roleLabel } from "@/lib/format";
import { api, ApiError, unwrap } from "./client";
import type { DailyDrop } from "./home";
import { useKey } from "./keys";
import { useMe } from "./me";

/** Why an intro could not be sent, in the words a screen needs. */
export type IntroFailure = "weekly_limit" | "target_full" | "no_path" | "under_18" | "failed";

export class IntroError extends Error {
  constructor(readonly failure: IntroFailure) { super(failure); }
}

function failureOf(e: unknown): IntroFailure {
  if (!(e instanceof ApiError)) return "failed";
  if (e.code === "intro_weekly_limit") return "weekly_limit";
  if (e.code === "target_full") return "target_full";
  if (e.code === "no_warm_path") return "no_path";
  if (e.status === 403) return "under_18";
  return "failed";
}

/** Who would make the introduction: a mutual ("via Meera, mentor") or nobody when you are already connected. */
export function useIntroPath(targetId: number | null) {
  const { key, enabled } = useKey("intro-path", targetId);
  return useQuery({
    queryKey: key,
    enabled: enabled && targetId !== null,
    retry: false,
    queryFn: async () => {
      let p;
      try { p = await unwrap(api.GET("/api/intros/path/{target_id}", { params: { path: { target_id: targetId! } } })); }
      catch (e) { throw new IntroError(failureOf(e)); }
      return { via: p.via ? { id: p.via.id, name: p.via.display_name, role: roleLabel(p.via.role) } : null };
    },
  });
}

/**
 * Asks for an intro (the backend routes it via a mutual if one exists). From the Daily Drop it also records the swipe, so the card
 * stays answered after a reload. Failures come back as an `IntroError` with a `failure` the sheet can put in one sentence.
 */
export function useRequestIntro() {
  const qc = useQueryClient();
  const { key: dropKey } = useKey("drop");
  return useMutation({
    mutationFn: async ({ id, fromDrop }: { id: number; fromDrop?: boolean }) => {
      try {
        await unwrap(api.POST("/api/intros", { body: { target_id: id, message: "" } }));
      } catch (e) {
        throw new IntroError(failureOf(e));
      }
      if (fromDrop) {
        try { await unwrap(api.POST("/api/drop/today/{member_id}/swipe", { params: { path: { member_id: id } }, body: { direction: "intro" } })); }
        catch { qc.invalidateQueries({ queryKey: dropKey }); } // the intro is sent; the card just comes back as "to answer" until the next load
      }
    },
    onSuccess: (_d, { id, fromDrop }) => {
      if (fromDrop) qc.setQueryData<DailyDrop>(dropKey, (old) => old && { ...old, cards: old.cards.map((c) => (c.id === id ? { ...c, answered: "intro" } : c)) });
    },
  });
}

export type IntroBox = "received" | "sent" | "brokered";

export type IntroRow = {
  id: number;
  /** Where the viewer stands in this intro. */
  myRole: "requester" | "broker" | "target";
  status: string;
  /** Whose turn it is: the mutual connection ("broker"), the person asked ("target"), or finished. */
  stage: string;
  /** The viewer is the one who has to answer now. */
  canRespond: boolean;
  requester: { id: number; name: string };
  target: { id: number; name: string };
  via: { id: number; name: string } | null;
  message: string;
  /** 1–5 once the person who asked has rated it. */
  rating: number | null;
  expiresAt: string;
  /** One line a list row can show under the names. */
  line: string;
};

const person = (p: { id: number; display_name: string }) => ({ id: p.id, name: p.display_name });

function introLine(i: { my_role: string; status: string; stage: string; via?: { display_name: string } | null; target: { display_name: string } }): string {
  if (i.status === "accepted" || i.status === "completed") return "Accepted";
  if (i.status === "declined") return "Not this time";
  if (i.status === "expired") return "Expired with no answer";
  if (i.my_role === "requester") return i.stage === "broker" && i.via ? `Waiting for ${i.via.display_name} to pass it on` : `Waiting for ${i.target.display_name}`;
  return "Waiting for your answer";
}

export function toIntroRow(i: Schemas["IntroOut"]): IntroRow {
  return {
    id: i.id,
    myRole: i.my_role,
    status: i.status,
    stage: i.stage,
    canRespond: i.can_respond,
    requester: person(i.requester),
    target: person(i.target),
    via: i.via ? person(i.via) : null,
    message: i.message,
    rating: i.outcome_rating ?? null,
    expiresAt: i.expires_at,
    line: introLine(i),
  };
}

/** Why answering or rating failed, in one sentence. */
export function introAnswerProblem(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === "not_your_turn") return "It isn't your turn on this one yet.";
    if (e.code === "intro_expired") return "This intro has expired.";
    if (e.code === "intro_not_accepted") return "You can rate it once it's accepted.";
  }
  return "Couldn't save that. Try again.";
}

/**
 * Intros the viewer is part of, one box at a time (`received` = asked of me, `brokered` = I'm the mutual connection, `sent` = I asked).
 * Members under 18 can't use intros (the server answers 403), so nothing is asked for them.
 */
export function useIntros(box: IntroBox) {
  const me = useMe().data;
  const { enabled } = useKey();
  const q = useQuery({
    queryKey: ["intros", box],
    enabled: enabled && !!me && !me.isMinor,
    queryFn: async () => (await unwrap(api.GET("/api/intros", { params: { query: { box, limit: 50 } } }))).items.map(toIntroRow),
  });
  return { rows: q.data ?? [], isPending: q.isPending && q.fetchStatus !== "idle", isError: q.isError, refetch: q.refetch };
}

/** Accept or decline an intro when it's your turn (the mutual connection answers first, then the person). Safe to repeat. */
export function useRespondIntro() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, accept }: { id: number; accept: boolean }) => unwrap(api.POST("/api/intros/{intro_id}/respond", { params: { path: { intro_id: id } }, body: { accept } })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["intros"] }); qc.invalidateQueries({ queryKey: ["unread"] }); },
  });
}

/** The person who asked rates an accepted intro 1–5. */
export function useRateIntro() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, rating }: { id: number; rating: number }) => unwrap(api.POST("/api/intros/{intro_id}/rating", { params: { path: { intro_id: id } }, body: { rating } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["intros"] }),
  });
}
