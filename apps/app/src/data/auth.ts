"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { BASE_PATH, SHOW_DEV_TOOLS } from "@/lib/env";
import { roleLabel } from "@/lib/format";
import { api, unwrap } from "./client";
import { MOCK } from "./mocks/config";
import { useSession } from "./session";
import { getSupabase, supabaseConfigured } from "./supabase";

export type Persona = { key: string; name: string; role: string };

/** Dev and demo only (F9): the people you can sign in as. Never asked for in staging or production. */
export function usePersonas() {
  return useQuery({
    queryKey: ["personas"],
    enabled: SHOW_DEV_TOOLS,
    staleTime: 5 * 60_000,
    queryFn: async (): Promise<Persona[]> =>
      (await unwrap(api.GET("/api/demo/personas"))).filter((p) => p.key !== "admin").map((p) => ({ key: p.key, name: p.display_name, role: roleLabel(p.role) })),
  });
}

export function usePersonaSignIn() {
  const { signInDemo } = useSession();
  return useMutation({
    mutationFn: async (persona: string) => (await unwrap(api.POST("/api/demo/token", { body: { persona } }))).access_token,
    onSuccess: (t) => signInDemo(t),
  });
}

const callbackUrl = () => `${window.location.origin}${BASE_PATH}/auth/callback`;

/** Google and email-code sign-in through Supabase. `available` is false until the project keys are in .env. */
export function useSupabaseSignIn() {
  const sb = () => {
    const c = getSupabase();
    if (!c) throw new Error("Sign-in isn't set up here yet.");
    return c;
  };
  const google = useMutation({
    mutationFn: async () => {
      const { data, error } = await sb().auth.signInWithOAuth({ provider: "google", options: { redirectTo: callbackUrl(), skipBrowserRedirect: true } });
      if (error) throw error;
      // Mock mode has no Google to visit: it comes straight back with a code, and the mock Supabase answers the exchange.
      window.location.assign(MOCK ? `${callbackUrl()}?code=mock-code` : data.url);
    },
  });
  const sendCode = useMutation({
    mutationFn: async (email: string) => {
      const { error } = await sb().auth.signInWithOtp({ email: email.trim(), options: { shouldCreateUser: true } });
      if (error) throw error;
    },
  });
  const verifyCode = useMutation({
    mutationFn: async ({ email, code }: { email: string; code: string }) => {
      const { error } = await sb().auth.verifyOtp({ email: email.trim(), token: code, type: "email" });
      if (error) throw error;
    },
  });
  return { available: supabaseConfigured, google, sendCode, verifyCode };
}
