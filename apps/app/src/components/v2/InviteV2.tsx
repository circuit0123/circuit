"use client";

import { BigHeadline, IconButton } from "@circuit/ui";
import { ChevronLeft } from "lucide-react";

type Props = {
  code: string;
  onCode: (v: string) => void;
  error: string | null;
  ready: boolean;
  pending: boolean;
  onSubmit: () => void;
  onWaitlist: () => void;
  onBack: () => void;
};

/** v2 invite-code screen (PMInvite.dc.html). The redeem logic and error messages stay in Invite.tsx. */
export function CodeV2({ code, onCode, error, ready, pending, onSubmit, onWaitlist, onBack }: Props) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col px-5 pb-[max(36px,env(safe-area-inset-bottom))] pt-5">
      <div className="flex items-center justify-between">
        <IconButton label="Back" onClick={onBack}><ChevronLeft size={18} strokeWidth={2.2} aria-hidden /></IconButton>
      </div>
      <BigHeadline first="Got an" second="invite code?" className="mt-9 text-[56px]" />
      <p className="mt-3.5 text-[15px] leading-[1.45] text-c-muted">Circuit is invite-only while we're in beta.</p>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }} className="mt-6 rounded-[18px] bg-c-hero p-4 text-c-hero-text">
        <label htmlFor="invite-code" className="font-mono text-[12px] uppercase text-c-hero-muted">Invite code</label>
        <input
          id="invite-code"
          value={code}
          onChange={(e) => onCode(e.target.value)}
          placeholder="CIRCUIT-0000"
          autoCapitalize="characters"
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          autoFocus
          aria-invalid={!!error}
          aria-describedby="invite-hint"
          className="mt-2 block h-14 w-full border-0 border-b-2 border-[#4a4a4a] bg-transparent font-mono text-[26px] font-medium tracking-[0.12em] text-c-hero-text outline-none placeholder:text-[#8a8d93] focus-visible:border-c-bright"
        />
        <div id="invite-hint" role={error ? "alert" : "status"} className={`mt-2.5 text-[13px] ${error ? "text-danger" : "text-c-hero-muted"}`}>{error ?? "Letters and numbers, no spaces"}</div>
      </form>
      <div className="mt-auto pt-10">
        <button type="button" disabled={!ready || pending} onClick={onSubmit} className="h-[52px] w-full rounded-[14px] bg-c-bright text-[16px] font-semibold text-c-bg disabled:bg-c-card disabled:text-c-muted">Continue</button>
        <button type="button" onClick={onWaitlist} className="mt-3.5 block min-h-11 w-full text-center text-[14px] text-c-muted underline">No code? Join the waitlist</button>
      </div>
    </main>
  );
}
