"use client";

import { useQuery } from "@tanstack/react-query";
import type { Appearance } from "./appearance";
import { api, unwrap } from "./client";
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
        location: m.lat != null && m.lng != null ? { lat: m.lat, lng: m.lng } : null,
      };
    },
  });
}
