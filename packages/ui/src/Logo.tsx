import { useId } from "react";
import { cx } from "./cx";
import { lockupDark, lockupLight, markDark, markLight } from "./logo-paths";

type Props = {
  /** `lockup` = mark + "circuit" wordmark; `mark` = the arch alone. */
  kind?: "lockup" | "mark";
  /** Rendered height in px. Never smaller than the minimum size (DESIGN.md §5): 20px for the mark, 88px wide for the lockup. */
  height?: number;
  className?: string;
};

const MIN_HEIGHT = { lockup: 22, mark: 20 } as const;

type Art = { viewBox: string; body: string };

function Svg({ art, id, height, className }: { art: Art; id: string; height: number; className: string }) {
  const [, , w, h] = art.viewBox.split(" ").map(Number);
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={art.viewBox}
      width={Math.round((height * w) / h)}
      height={height}
      role="img"
      aria-label="Circuit"
      className={className}
      // Static, trusted markup copied from docs/brand/svg: the logo is never redrawn or recoloured here.
      dangerouslySetInnerHTML={{ __html: art.body.replaceAll("__ID__", id) }}
    />
  );
}

/** The Bridge logo. Shows the on-dark file in the dark theme and the on-light file in the light theme, with CSS only (no flash, no JS). */
export function Logo({ kind = "lockup", height = 32, className }: Props) {
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");
  const h = Math.max(height, MIN_HEIGHT[kind]);
  const [dark, light] = kind === "lockup" ? [lockupDark, lockupLight] : [markDark, markLight];
  return (
    <>
      <Svg art={dark} id={`m${uid}d`} height={h} className={cx("only-dark", className)} />
      <Svg art={light} id={`m${uid}l`} height={h} className={cx("only-light", className)} />
    </>
  );
}
