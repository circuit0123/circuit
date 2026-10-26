"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { roleLabel } from "@/lib/format";
import { api, ApiError, unwrap } from "./client";
import type { DailyDrop } from "./home";
import { useKey } from "./keys";

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
