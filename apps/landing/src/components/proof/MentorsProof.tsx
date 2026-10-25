import { Example } from "../Example";
import { Proof } from "./Proof";

/** One anonymised circuit: three roles, no names. Each gives one thing and gets one thing, and the last gift comes back to the first person. */
const LEGS = [
  { who: "A marketer", gives: "marketing help", gets: "help with fundraising" },
  { who: "A founder", gives: "hiring advice", gets: "marketing help" },
  { who: "A mentor", gives: "fundraising advice", gets: "hiring advice" },
] as const;

export function MentorsProof() {
  return (
    <Proof heading="Everyone gives one thing and gets one thing" lede="A circuit is three people in a loop. Nobody is asked to give without getting, and nothing starts until all three have said yes.">
      <Example>
        <ol className="grid gap-4 lg:grid-cols-3">
          {LEGS.map((l, i) => (
            <li key={l.who} className="rounded-card bg-bg p-surface">
              <p className="t-headline">{l.who}</p>
              <p className="mt-3 t-body">Gives {l.gives}</p>
              <p className="mt-1 t-body text-text-muted">Gets {l.gets}</p>
              <p className="mt-3 t-subhead text-text-muted">{i === LEGS.length - 1 ? "Back to the marketer: the loop closes." : "Then on to the next person."}</p>
            </li>
          ))}
        </ol>
      </Example>
    </Proof>
  );
}
