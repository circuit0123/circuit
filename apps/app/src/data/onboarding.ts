"use client";

import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import { useKey } from "./keys";

export type OnboardingState = {
  branch: "default" | "investor" | "partner";
  steps: string[];
  skip: string[];
  currentStep: string | null;
  completed: boolean;
  answers: Record<string, unknown>;
  signupSource: string;
};

/** Where the person is in onboarding. One call; the screen order and the skips come from the server. */
export function useOnboardingState(enabled = true) {
  const k = useKey("onboarding");
  return useQuery({
    queryKey: k.key,
    enabled: k.enabled && enabled,
    queryFn: async (): Promise<OnboardingState> => {
      const s = await unwrap(api.GET("/api/onboarding/state"));
      return {
        branch: s.branch,
        steps: s.steps,
        skip: s.skip,
        currentStep: s.current_step,
        completed: !!s.completed_at,
        answers: s.answers as Record<string, unknown>,
        signupSource: s.signup_source,
      };
    },
  });
}
