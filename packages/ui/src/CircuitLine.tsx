import { cx } from "./cx";

export type Station = { label: string; sub?: string; you?: boolean };

// A closed loop with 45° corners. Stations sit at fixed spots on the path.
const LOOP = "M64 56H296L320 80V140L296 164H64L40 140V80Z";
const SPOTS = [
  { x: 100, y: 56, labelY: 22 },
  { x: 260, y: 56, labelY: 22 },
  { x: 180, y: 164, labelY: 198 },
];
// Direction chevrons: where each handover happens along the loop.
const CHEVRONS = [
  { x: 180, y: 56, rot: 0 },
  { x: 320, y: 110, rot: 90 },
  { x: 40, y: 110, rot: -90 },
];

/**
 * The circuit line motif (DESIGN.md): three stations on a closed loop; each handover runs
 * clockwise from one station to the next. `animate` draws the line once.
 */
export function CircuitLine({ stations, animate = false, className, title }: { stations: Station[]; animate?: boolean; className?: string; title: string }) {
  const s = stations.slice(0, 3);
  return (
    <svg viewBox="24 0 312 226" role="img" aria-label={title} className={cx("h-auto w-full max-w-[440px]", className)}>
      <path d={LOOP} pathLength={1} fill="none" stroke="var(--color-line)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className={animate ? "circuit-draw" : undefined} />
      {CHEVRONS.slice(0, s.length).map((c, i) => (
        <path key={i} d="M-5 -5 2 0-5 5" transform={`translate(${c.x} ${c.y}) rotate(${c.rot})`} fill="none" stroke="var(--color-line)" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      ))}
      {s.map((st, i) => (
        <g key={i}>
          <circle cx={SPOTS[i].x} cy={SPOTS[i].y} r={7} fill={st.you ? "var(--color-line)" : "var(--color-surface)"} stroke="var(--color-line)" strokeWidth={2} />
          <text x={SPOTS[i].x} y={SPOTS[i].labelY} textAnchor="middle" fontSize={17} fontWeight={600} fill="var(--color-ink)">{st.label}</text>
          {st.sub && (
            <text x={SPOTS[i].x} y={SPOTS[i].labelY + 19} textAnchor="middle" fontSize={15} fill="var(--color-ink-soft)">{st.sub}</text>
          )}
        </g>
      ))}
    </svg>
  );
}

/** Short divider: a line with one station. */
export function LineDivider({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 96 12" width={96} height={12} aria-hidden="true" className={className}>
      <path d="M0 6H40M56 6H96" stroke="var(--color-line)" strokeWidth={2} strokeLinecap="round" />
      <circle cx={48} cy={6} r={5} fill="var(--color-surface)" stroke="var(--color-line)" strokeWidth={2} />
    </svg>
  );
}
