"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Appearance } from "./appearance";
import { api, ApiError, unwrap } from "./client";
import { useKey } from "./keys";

export type Me = {
  id: number;
  name: string;
  role: "student" | "founder" | "mentor" | "investor" | "partner_admin" | "super_admin";
  city: string;
  college: string;
  bio: string;
  level: number;
  isMinor: boolean;
  organisationId: number | null;
  betaAccess: boolean;
  needsConsent: boolean;
  policyVersion: string;
  appearance: Appearance;
  allowRequests: boolean;
  location: { lat: number; lng: number } | null;
  /** The profile photo's address, or null for the circuit-pattern avatar. */
  photo: string | null;
};

/** The signed-in member. Not behind the beta or consent gates, so it works on every gate screen. */
export function useMe() {
  const { key, enabled } = useKey("me");
  return useQuery({
    queryKey: key,
    enabled,
    queryFn: async (): Promise<Me> => {
      const m = await unwrap(api.GET("/api/me"));
      return {
        id: m.id,
        name: m.display_name,
        role: m.role as Me["role"],
        city: m.city,
        college: m.college,
        bio: m.bio,
        level: m.verification_level,
        isMinor: m.is_minor,
        organisationId: m.organisation_id,
        betaAccess: m.beta_access,
        needsConsent: m.needs_consent,
        policyVersion: m.policy_version,
        appearance: { theme: m.appearance.theme, accent: m.appearance.accent, swipeTabs: m.appearance.swipe_tabs },
        allowRequests: m.allow_requests,
        photo: m.photo ?? null,
        location: m.lat != null && m.lng != null ? { lat: m.lat, lng: m.lng } : null,
      };
    },
  });
}

/**
 * Verification level 2 (CLAUDE.md F7): a code goes to a work email (not a personal mailbox); entering it raises the level. The server's
 * sentence for a refused address ("Use your work email, not a personal one.") is passed on as it is.
 */
export function useWorkEmail() {
  const qc = useQueryClient();
  const start = useMutation({ mutationFn: (email: string) => unwrap(api.POST("/api/me/verify/work-email", { body: { email } })) });
  const confirm = useMutation({
    mutationFn: (code: string) => unwrap(api.POST("/api/me/verify/work-email/confirm", { body: { code } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["me"] }),
  });
  return { start, confirm };
}

/** One sentence for why a work-email step failed: the server's own words for a refused address or code, a generic line for the rest. */
export const workEmailProblem = (e: unknown): string | null =>
  !e ? null : e instanceof ApiError && e.status < 500 && e.message ? e.message : "Couldn't do that. Check your connection and try again.";
