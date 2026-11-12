"use client";

import { Avatar, EmeraldBand, VerifiedBadge } from "@circuit/ui";

/** "Asha Raman" → ["Asha", "Raman."]. A single word stays on one line. */
function splitName(name: string): [string, string | null] {
  const words = name.trim().split(/\s+/);
  if (words.length < 2) return [name, null];
  return [words[0], `${words.slice(1).join(" ")}.`];
}

type Props = { id: number; name: string; level: number; line: string; org?: string | null; photo: string | null; children?: React.ReactNode };

/** The profile banner (PMProfile.dc.html): a grey panel with one emerald slash, the name in two lines (second outlined) and the avatar. */
export function ProfileHeroV2({ id, name, level, line, org, photo, children }: Props) {
  const [a, b] = splitName(name);
  return (
    <section aria-label={name} className="relative overflow-hidden border-b border-c-border bg-c-card px-5 pb-5 pt-6">
      <EmeraldBand className="-top-10 right-10 h-[420px] w-[90px]" rotate={20} />
      <div className="relative flex items-end justify-between gap-3">
        <h1 className="m-0 min-w-0 text-[clamp(36px,13vw,56px)] font-bold leading-[0.92] tracking-[-0.06em] [overflow-wrap:anywhere]">
          {a}
          {b && (<><br /><span style={{ color: "transparent", WebkitTextStroke: "1.5px var(--c-muted)" }}>{b}</span></>)}
        </h1>
        <span className="shrink-0 rounded-full border-[3px] border-c-bg"><Avatar id={id} name={name} src={photo} size={96} /></span>
      </div>
      <p className="relative mt-3.5 flex flex-wrap items-center gap-1.5 text-[14px] text-c-muted">{line}<VerifiedBadge level={level} /></p>
      {org && <p className="relative text-[14px] text-c-muted">{org}</p>}
      {children}
    </section>
  );
}
