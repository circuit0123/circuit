import { Container } from "./Container";

export type PilotStats = { city: string; startups: number; openRoles: number; circuitsClosed: number };

/** "Live in <city>" with real counts. Renders NOTHING until real, meaningful numbers are passed in: never fake figures (DESIGN.md §4, §12).
 *  The home page passes `null` today because there is no public stats endpoint yet. */
export function PilotCity({ stats }: { stats: PilotStats | null }) {
  if (!stats) return null;
  const items = [
    { n: stats.startups, label: "startups" },
    { n: stats.openRoles, label: "open roles" },
    { n: stats.circuitsClosed, label: "circuits closed" },
  ];
  return (
    <section aria-labelledby="pilot-h">
      <Container className="pb-20 lg:pb-[120px]">
        <div className="rounded-sheet bg-surface p-6 lg:p-12">
          <h2 id="pilot-h" className="t-title1">Live in {stats.city}</h2>
          <dl className="mt-6 flex flex-wrap gap-x-12 gap-y-6">
            {items.map((i) => (
              <div key={i.label}>
                <dd className="num t-title2">{i.n}</dd>
                <dt className="t-subhead text-text-muted">{i.label}</dt>
              </div>
            ))}
          </dl>
        </div>
      </Container>
    </section>
  );
}
