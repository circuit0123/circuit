import { CircleDot, Handshake, MapPin, MoreHorizontal, Store } from "lucide-react";
import { Chip } from "./Chip";
import { Button } from "./Button";
import type { RoleView } from "./types";

/** A role near you, as a feed row (no box). The title is the loud thing; the whole row opens the role. */
export function RoleCard({ role, onOpen, eyebrow = "Hiring near you" }: { role: RoleView; onOpen: () => void; /** The small line above the title; null leaves it out (a promoted role carries its own label). */ eyebrow?: string | null }) {
  return (
    <button type="button" onClick={onOpen} className="flex w-full flex-col items-start gap-1 px-4 text-left lg:px-0">
      {eyebrow && <span className="t-caption flex items-center gap-1 text-text-muted"><MapPin size={14} strokeWidth={1.75} aria-hidden /> {eyebrow}</span>}
      <span className="t-headline">{role.title}</span>
      <span className="t-body text-text-muted">{role.startup}, {role.place}</span>
      <span className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 t-subhead">
        {role.stipend && <span className="num">{role.stipend}</span>}
        {role.km !== null && <span className="num text-text-muted">{role.km < 10 ? role.km.toFixed(1) : Math.round(role.km)} km</span>}
        {role.match !== null && role.match >= 55 && <span className="num font-semibold">{role.match}% match</span>}
      </span>
      {role.tags.length > 0 && <span className="mt-2 flex flex-wrap gap-2">{role.tags.map((t) => <Chip key={t} label={t} />)}</span>}
    </button>
  );
}

const ICONS = { circuit_completed: CircleDot, intro_accepted: Handshake, startup_claimed: Store } as const;

export function ActivityCard({ type, text }: { type: keyof typeof ICONS; text: string }) {
  const Icon = ICONS[type];
  return (
    <div className="flex items-center gap-4 px-4 lg:px-0">
      <Icon size={20} strokeWidth={1.75} className="shrink-0 text-text-muted" aria-hidden />
      <p className="t-body max-w-[540px]">{text}</p>
    </div>
  );
}

/** A paid role in its own slot (DESIGN.md §4 "Promoted items"): the normal role row under a "Promoted" label and the startup's name, with a "…" for "Why am I seeing this?" and "Hide this". Never styled as a match. */
export function PromotedItem({ startup, role, onOpen, onMenu }: { startup: string; role: RoleView; onOpen: () => void; onMenu: () => void }) {
  return (
    <div>
      <div className="flex items-center justify-between gap-4 px-4 lg:px-0">
        <p className="t-subhead text-text-muted">Promoted · {startup}</p>
        <button type="button" onClick={onMenu} aria-label="About this promotion" className="-mr-2 flex h-11 w-11 items-center justify-center rounded-full text-text-muted lg:mr-0">
          <MoreHorizontal size={20} strokeWidth={1.75} />
        </button>
      </div>
      <RoleCard role={role} onOpen={onOpen} eyebrow={null} />
    </div>
  );
}

/** A call, event or announcement from a partner organisation: free, labelled "From {org}", and not a promotion. */
export function PartnerItem({ org, text }: { org: string; text: string }) {
  return (
    <div className="flex flex-col gap-1 px-4 lg:px-0">
      <p className="t-subhead text-text-muted">From {org}</p>
      <p className="t-body max-w-[540px]">{text}</p>
    </div>
  );
}

export function SkillsInDemandCard({ skills }: { skills: Array<{ name: string; roles: number }> }) {
  return (
    <div>
      <h3 className="t-title3">Skills in demand near you</h3>
      <ul className="mt-3 divide-y divide-separator">
        {skills.map((s) => (
          <li key={s.name} className="flex min-h-row items-center justify-between gap-4">
            <span className="t-body">{s.name}</span>
            <span className="t-footnote text-text-muted"><span className="num font-semibold text-text">{s.roles}</span> open roles</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CaughtUp({ onEarlier, onDiscover }: { onEarlier?: () => void; onDiscover: () => void }) {
  return (
    <div className="flex flex-col items-start gap-1 px-4 pb-8 pt-surface lg:px-0">
      <p className="text-[22px] font-medium leading-tight tracking-[-0.012em]">You're caught up.</p>
      <p className="t-body max-w-[36ch] text-text-muted">That's everything from the last week. Look for people and startups near you in Discover.</p>
      <div className="mt-3 flex flex-wrap gap-3">
        <Button variant="secondary" onClick={onDiscover}>Go to Discover</Button>
        {onEarlier && <Button variant="text" className="px-2" onClick={onEarlier}>See earlier this week</Button>}
      </div>
    </div>
  );
}
