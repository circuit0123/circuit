import { Avatar } from "./Avatar";
import { BridgeBadge, VerifiedBadge } from "./Badge";
import { Button } from "./Button";
import { MatchStrength, type Strength } from "./MatchStrength";
import { cx } from "./cx";
import type { Person } from "./types";

export type MatchView = { id: number; person: Person; strength: Strength | null; reason: string; bridge: boolean };

type Props = {
  match: MatchView;
  onOpen: () => void;
  onIntro?: () => void;
  /** Disables the Intro button after it was sent. */
  asked?: boolean;
  className?: string;
};

/** A person worth meeting. The reason comes first (DESIGN.md §4 Home), then who they are; strength is words, never a number. */
export function MatchCard({ match, onOpen, onIntro, asked, className }: Props) {
  const p = match.person;
  return (
    <article className={cx("flex flex-col gap-3 rounded-card border border-separator bg-surface p-4", className)}>
      <p className="t-callout">{match.reason}</p>
      <div className="flex items-center gap-3">
        <Avatar id={p.id} name={p.name} size={44} />
        <button type="button" onClick={onOpen} className="min-w-0 flex-1 text-left">
          <span className="t-headline flex items-center gap-1 truncate">
            <span className="truncate">{p.name}</span>
            <VerifiedBadge level={p.level} />
          </span>
          <span className="t-footnote block truncate text-text-muted">{[p.role, p.place].filter(Boolean).join(" · ")}</span>
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <MatchStrength strength={match.strength} />
        {match.bridge && <BridgeBadge />}
        {onIntro && (
          <Button className="ml-auto min-h-11 px-4" disabled={asked} onClick={onIntro}>
            {asked ? "Intro asked" : "Intro me"}
          </Button>
        )}
      </div>
    </article>
  );
}
