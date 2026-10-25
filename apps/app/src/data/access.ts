"use client";

import { useMutation, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api, unwrap } from "./client";
import { problemOf } from "./errors";
import { useMe } from "./me";
import { useJoinContext } from "./join";
import { useSession } from "./session";

/** Who-am-I and the config decide which gate screen shows; after consent or an invite code they are asked again. */
const askAgain = (qc: QueryClient) => qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === "me" || q.queryKey[1] === "config" || q.queryKey[0] === "onboarding" });

/** Accepting the current terms and privacy policy (the consent screen). */
export function useConsent() {
  const qc = useQueryClient();
  const policy = useMe().data?.policyVersion ?? "";
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/me/consent", { body: { policy_version: policy } })),
    onSuccess: () => askAgain(qc),
  });
}

/** One sentence for a failed invite code. The server answers every bad code the same way, so we do too. */
export function inviteMessage(e: unknown): string {
  const p = problemOf(e);
  if (p.kind === "rate_limited") return p.message;
  if (p.kind === "network") return p.message;
  return "That code didn't work. Check it, or ask whoever invited you for a new one.";
}

/** Using an invite code. Success moves the person on through the gate (an organisation code also joins them to it). */
export function useRedeem() {
  const qc = useQueryClient();
  const join = useJoinContext();
  return useMutation({
    mutationFn: (code: string) => unwrap(api.POST("/api/beta/redeem", { body: { code: code.trim() } })),
    onSuccess: async () => {
      join.forget("code");
      await askAgain(qc);
    },
  });
}

/** Joining the waitlist from the invite screen. The answer is the same whether or not the email was already listed. */
export function useJoinWaitlist() {
  const { identity } = useSession();
  const join = useJoinContext();
  const m = useMutation({
    mutationFn: ({ email, role, city, college }: { email: string; role: string; city?: string; college?: string }) =>
      unwrap(api.POST("/api/waitlist", { body: { email, role: role as "student", city: city ?? "", college: college ?? "", note: "", src: join.src ?? "app" } })),
  });
  return { ...m, email: identity?.email ?? "", role: join.role };
}

/**
 * An invite link carries its code (`/join?code=…`): when the gate wants one and we already have it, use it without showing the screen.
 * If it fails the screen appears with the code filled in and one sentence saying why.
 */
export function useInviteLink() {
  const join = useJoinContext();
  const redeem = useRedeem();
  const tried = useRef(false);
  const [failed, setFailed] = useState<{ code: string; error: string } | null>(null);
  const code = join.code;
  useEffect(() => {
    if (!code || tried.current) return;
    tried.current = true;
    redeem.mutate(code, {
      onError: (e) => { setFailed({ code, error: inviteMessage(e) }); join.forget("code"); },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once per screen, whatever re-renders happen
  }, [code]);
  return { checking: !!code && !failed, failed };
}
