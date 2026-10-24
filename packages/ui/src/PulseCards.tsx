import { CircleDot, Handshake, MapPin, Store } from "lucide-react";
import { Card } from "./Card";
import { Chip } from "./Chip";
import { Button } from "./Button";
import type { RoleView } from "./types";

export function RoleCard({ role, onOpen }: { role: RoleView; onOpen: () => void }) {
  return (
    <Card className="mx-4 p-4 lg:mx-0">
      <p className="t-footnote flex items-center gap-1 text-text-muted"><MapPin size={14} strokeWidth={1.75} aria-hidden /> Hiring near you</p>
      <h3 className="t-headline mt-2">{role.title}</h3>
      <p className="t-body text-text-muted">{role.startup}, {role.place}</p>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 t-footnote">
        {role.stipend && <span className="num">{role.stipend}</span>}
        {role.km !== null && <span className="num text-text-muted">{role.km < 10 ? role.km.toFixed(1) : Math.round(role.km)} km</span>}
        {role.match !== null && role.match >= 55 && <span className="num font-semibold">{role.match}% match</span>}
      </div>
      {role.tags.length > 0 && <div className="mt-3 flex flex-wrap gap-2">{role.tags.map((t) => <Chip key={t} label={t} />)}</div>}
      <Button className="mt-4 w-full" onClick={onOpen}>See role</Button>
    </Card>
  );
}

const ICONS = { circuit_completed: CircleDot, intro_accepted: Handshake, startup_claimed: Store } as const;

export function ActivityCard({ type, text }: { type: keyof typeof ICONS; text: string }) {
  const Icon = ICONS[type];
  return (
    <div className="mx-4 flex items-center gap-3 rounded-card bg-surface-2 px-4 py-3 lg:mx-0">
      <Icon size={20} strokeWidth={1.75} className="shrink-0 text-text-muted" aria-hidden />
      <p className="t-body">{text}</p>
    </div>
  );
}

export function SkillsInDemandCard({ skills }: { skills: Array<{ name: string; roles: number }> }) {
  return (
    <Card className="mx-4 p-4 lg:mx-0">
      <h3 className="t-headline">Skills in demand near you</h3>
      <ul className="mt-3 divide-y divide-border">
        {skills.map((s) => (
          <li key={s.name} className="flex items-baseline justify-between gap-4 py-2">
            <span className="t-body">{s.name}</span>
            <span className="t-footnote text-text-muted"><span className="num font-semibold text-text">{s.roles}</span> open roles</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export function CaughtUp({ onEarlier, onDiscover }: { onEarlier?: () => void; onDiscover: () => void }) {
  return (
    <div className="flex flex-col items-start gap-1 px-4 py-8 lg:px-0">
      <p className="t-title2">You're caught up.</p>
      <p className="t-body max-w-[36ch] text-text-muted">That's everything from the last week. Look for people and startups near you in Discover.</p>
      <div className="mt-3 flex flex-wrap gap-3">
        <Button variant="secondary" onClick={onDiscover}>Go to Discover</Button>
        {onEarlier && <Button variant="ghost" className="px-2" onClick={onEarlier}>See earlier this week</Button>}
      </div>
    </div>
  );
}
