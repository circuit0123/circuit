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

/** A person worth meeting, as a row (no box). The reason comes first (DESIGN.md §4 Home), shown whole; then who they are. Strength is words. */
export function MatchCard({ match, onOpen, onIntro, asked, className }: Props) {
  const p = match.person;
  return (
    <article className={cx("flex flex-col gap-3", className)}>
      <p className="t-body max-w-[540px]">{match.reason}</p>
      <div className="flex min-h-row-sub items-center gap-4">
        <Avatar id={p.id} name={p.name} size={44} />
        <button type="button" onClick={onOpen} className="min-w-0 flex-1 text-left">
          <span className="t-headline flex items-center gap-1">
            <span>{p.name}</span>
            <VerifiedBadge level={p.level} />
          </span>
          <span className="t-footnote block text-text-muted">{[p.role, p.place].filter(Boolean).join(" · ")}</span>
        </button>
        {onIntro && (
          <Button className="min-h-11 px-4" disabled={asked} onClick={onIntro}>
            {asked ? "Intro asked" : "Intro me"}
          </Button>
        )}
      </div>
      {(match.strength || match.bridge) && (
        <div className="flex flex-wrap items-center gap-2">
          <MatchStrength strength={match.strength} />
          {match.bridge && <BridgeBadge />}
        </div>
      )}
    </article>
  );
}
