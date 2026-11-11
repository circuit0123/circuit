"use client";

import { BigHeadline, EmeraldBand, LogoV2, MonoLabel } from "@circuit/ui";
import { useFeatures } from "@/data";
import { Legal } from "../Legal";

type Props = {
  pending: boolean;
  googleError: string | null;
  onGoogle: () => void;
  onEmail: () => void;
  /** Dev and demo persona picker, passed in so the v1 logic is reused as is. */
  personas: React.ReactNode;
};

/** v2 welcome screen (PMWelcome.dc.html). The email and code steps after it are the shared Step screens in v2 colours. */
export function WelcomeV2({ pending, googleError, onGoogle, onEmail, personas }: Props) {
  const { betaMode } = useFeatures();
  return (
    <main className="relative mx-auto flex min-h-dvh w-full max-w-[440px] flex-col overflow-hidden px-5 pb-[max(36px,env(safe-area-inset-bottom))] pt-7">
      <EmeraldBand className="-left-16 top-[250px] h-[110px] w-[560px]" rotate={-9} />
      <div className="relative flex items-center">
        <LogoV2 height={24} />
        {betaMode && <MonoLabel className="ml-auto">Invite-only beta</MonoLabel>}
      </div>
      <BigHeadline first="Build with" second="people near you." className="relative mt-16 text-[60px]" />
      <p className="relative mt-5 text-[17px] leading-[1.45] text-c-text">Find work, collaborators and mentors who need what you're good at.</p>
      <div className="relative">{personas}</div>
      <div className="relative mt-auto flex flex-col gap-2.5 pt-10">
        <button type="button" disabled={pending} onClick={onGoogle} className="h-[52px] rounded-[14px] bg-c-hero text-[16px] font-semibold text-c-hero-text disabled:opacity-50">Continue with Google</button>
        {googleError && <p role="alert" className="text-[13px] text-danger">{googleError}</p>}
        <button type="button" onClick={onEmail} className="h-[52px] rounded-[14px] border border-c-border bg-c-card text-[16px] font-semibold text-c-text">Continue with email</button>
        <div className="mt-1 text-c-muted [&_p]:text-[12px]"><Legal /></div>
      </div>
    </main>
  );
}
