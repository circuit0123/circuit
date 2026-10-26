import { SCREEN_SIZE, SCREENS } from "@/content/screens";
import type { Step } from "@/content/types";

/** The shape of an app screenshot: a phone screen, 39:64. Placeholders use the same frame so a page doesn't shift when the real image arrives. */
export const SHOT_FRAME = "relative aspect-[39/64] overflow-hidden rounded-sheet bg-surface";
const WIDE_FRAME = "relative aspect-[16/10] overflow-hidden rounded-card bg-bg";

/** A frame that says plainly which app screen is still to come (never a fake screenshot). */
export function ShotPlaceholder({ screen, wide }: { screen: string; wide?: boolean }) {
  return (
    <div role="img" aria-label={`App screenshot coming: ${screen} screen`} className={`${wide ? WIDE_FRAME : SHOT_FRAME} flex items-center justify-center p-6 text-center t-subhead text-text-subtle`}>
      App screenshot coming: {screen}
    </div>
  );
}

/** A real app screenshot (dark and light versions, AVIF with a WebP fallback), or a labelled placeholder when that screen isn't built yet. */
export function Shot({ step }: { step: Pick<Step, "shot" | "alt" | "missing" | "screen"> }) {
  if (step.screen) {
    const s = `/screens/${step.screen}`;
    return (
      <div className={SHOT_FRAME}>
        <picture>
          <source srcSet={`${s}.avif`} type="image/avif" />
          <source srcSet={`${s}.webp`} type="image/webp" />
          <img src={`${s}.png`} width={SCREEN_SIZE.width} height={SCREEN_SIZE.height} alt={SCREENS[step.screen].alt} loading="lazy" decoding="async" className="h-full w-full object-cover object-top" />
        </picture>
      </div>
    );
  }
  if (!step.shot) return <ShotPlaceholder screen={step.missing} />;
  const s = `/shots/${step.shot}`;
  return (
    <div className={SHOT_FRAME}>
      <picture>
        <source media="(prefers-color-scheme: light)" srcSet={`${s}-light.avif`} type="image/avif" />
        <source media="(prefers-color-scheme: light)" srcSet={`${s}-light.webp`} type="image/webp" />
        <source srcSet={`${s}-dark.avif`} type="image/avif" />
        <img src={`${s}-dark.webp`} width={780} height={1280} alt={step.alt} loading="lazy" decoding="async" className="h-full w-full object-cover object-top" />
      </picture>
    </div>
  );
}
