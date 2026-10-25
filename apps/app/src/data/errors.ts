import { ApiError } from "./client";

/** What a screen should do about a failed call. One mapping for the whole app. */
export type ProblemKind =
  | "network" | "signed_out" | "consent" | "beta" | "not_found" | "rate_limited" | "forbidden" | "invalid" | "unknown";

export type Problem = { kind: ProblemKind; code: string; message: string };

export function problemOf(e: unknown): Problem {
  if (!(e instanceof ApiError)) return { kind: "unknown", code: "unknown", message: "Something went wrong. Try again." };
  const { status, code } = e;
  const make = (kind: ProblemKind, message: string): Problem => ({ kind, code, message });
  if (status === 0) return make("network", "Can't reach Circuit. Check your connection and try again.");
  if (status === 401 || code === "account_deleted" || code === "account_suspended") return make("signed_out", "Please sign in again.");
  if (code === "consent_required") return make("consent", e.message);
  if (code === "beta_required") return make("beta", e.message);
  if (code === "rate_limited" || status === 429) return make("rate_limited", "That's a lot of tries. Wait a little and try again.");
  if (status === 404 || code === "feature_off") return make("not_found", "We couldn't find that.");
  if (status === 403) return make("forbidden", e.message);
  if (status === 400 || status === 422) return make("invalid", e.message);
  return make("unknown", e.message || "Something went wrong. Try again.");
}

/** Sentence for an error state: what happened and what to do (DESIGN.md §9). */
export const loadFailed = (what: string) => `Couldn't load ${what}. Check your connection and pull to refresh.`;

/** For screens: the problem behind a failed query or mutation, or null. `kind === "network"` means show an ErrorState with Try again. */
export const useProblem = (error: unknown): Problem | null => (error ? problemOf(error) : null);
