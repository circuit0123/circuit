import { cx } from "./cx";
import { circuitPattern } from "./pattern";
import { initials } from "./theme";

export type AvatarSize = 20 | 32 | 40 | 44 | 64 | 96 | 128;

type Props = {
  /** Seeds the pattern, so the same member always looks the same. */
  id: string | number;
  name: string;
  src?: string | null;
  size?: AvatarSize;
  shape?: "round" | "square";
  className?: string;
};

/** A photo, or a circuit pattern from the member id with the first initial small in a corner. Never a silhouette or big initials. */
export function Avatar({ id, name, src, size = 40, shape = "round", className }: Props) {
  const radius = shape === "round" ? "rounded-full" : "rounded-card";
  return (
    <span className={cx("relative inline-flex shrink-0 overflow-hidden", radius, className)} style={{ width: size, height: size }} aria-hidden>
      {src ? <img src={src} alt="" className="h-full w-full object-cover" /> : <PatternArt id={id} initial={size > 20 ? initials(name)[0] : null} size={size} />}
    </span>
  );
}

/** The pattern alone. `banner` fills a wide area (a Daily Drop card without a photo) with more traces. */
export function PatternArt({ id, initial, size, banner = false }: { id: string | number; initial?: string | null; size?: number; banner?: boolean }) {
  const p = circuitPattern(id, banner);
  const wide = banner ? 2.6 : (size ?? 128) >= 64 ? 2.4 : 3;
  const node = banner ? 1.5 : 1.8;
  const thin = banner ? 0.6 : 0.9;
  return (
    <svg viewBox={`0 0 ${p.w} ${p.h}`} preserveAspectRatio="xMidYMid slice" className="h-full w-full" focusable="false" aria-hidden>
      <rect width={p.w} height={p.h} fill={p.bg} />
      {p.traces.map((t, i) => (
        <polyline key={`w${i}`} points={t} fill="none" stroke={p.wide} strokeWidth={wide + (banner ? 1 : 1.6)} strokeLinejoin="round" strokeLinecap="round" />
      ))}
      {p.traces.map((t, i) => (
        <polyline key={`l${i}`} points={t} fill="none" stroke={p.line} strokeOpacity={0.55} strokeWidth={thin} strokeLinejoin="round" strokeLinecap="round" />
      ))}
      {p.nodes.map((n, i) => (
        <circle key={i} cx={n.x} cy={n.y} r={node} fill={p.bg} stroke={p.line} strokeWidth={thin} />
      ))}
      {initial && banner && <rect x="1" y={p.h - 8} width="6" height="7" rx="1.2" fill={p.bg} />}
      {initial && (
        <text x="2.2" y={p.h - 2} fontSize={banner ? 5 : size && size >= 64 ? 6 : 8} fontWeight={600} fill={p.line} fontFamily="var(--font-geist-sans), system-ui, sans-serif">
          {initial}
        </text>
      )}
    </svg>
  );
}
