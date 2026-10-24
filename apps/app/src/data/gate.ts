"use client";

import { problemOf } from "./errors";
import { useFeatures } from "./features";
import { useMe } from "./me";
import { useOnboardingState } from "./onboarding";
import { useSession } from "./session";

export type Gate = "loading" | "signed_out" | "consent" | "invite" | "onboarding" | "ready" | "error";

/**
 * Which screen the person belongs on right now. Order matches the API: sign-in, then consent
 * (checked first), then the beta invite, then onboarding. Persona sessions (dev/demo) are seeded
 * members, so they skip the onboarding gate; they can still open /onboarding by hand.
 */
export function useGate(): { gate: Gate; retry: () => void } {
  const { ready, token, source } = useSession();
  const features = useFeatures();
  const me = useMe();
  const consentOk = !!me.data && !me.data.needsConsent;
  const betaOk = consentOk && (!features.betaMode || me.data!.betaAccess);
  const onboarding = useOnboardingState(betaOk && source !== "demo");

  const retry = () => { void me.refetch(); void onboarding.refetch(); };
  if (!ready) return { gate: "loading", retry };
  if (!token) return { gate: "signed_out", retry };
  if (me.isError) return { gate: problemOf(me.error).kind === "signed_out" ? "signed_out" : "error", retry };
  if (me.isPending || !features.ready) return { gate: features.isError ? "error" : "loading", retry };
  if (me.data.needsConsent) return { gate: "consent", retry };
  if (!betaOk) return { gate: "invite", retry };
  if (source === "demo") return { gate: "ready", retry };
  if (onboarding.isError) return { gate: "error", retry };
  if (onboarding.isPending) return { gate: "loading", retry };
  return { gate: onboarding.data.completed ? "ready" : "onboarding", retry };
}
