import { SCREEN_SIZE, SCREENS, type ScreenId } from "@/content/screens";
import { Container } from "./Container";

const COLUMNS = { 1: "lg:grid-cols-1 lg:max-w-[260px]", 2: "lg:grid-cols-2 lg:max-w-[560px]", 3: "lg:grid-cols-3 lg:max-w-[840px]", 4: "lg:grid-cols-4" } as const;

/** One app screen in a plain CSS phone frame (no brand, no notch). The pictures are always dark; the frame follows the page theme. AVIF, then WebP, then PNG. */
function Phone({ id }: { id: ScreenId }) {
  const src = `/screens/${id}`;
  return (
    <figure>
      <div className="overflow-hidden rounded-[34px] border-[6px] border-surface-3">
        <picture>
          <source srcSet={`${src}.avif`} type="image/avif" />
          <source srcSet={`${src}.webp`} type="image/webp" />
          <img src={`${src}.png`} width={SCREEN_SIZE.width} height={SCREEN_SIZE.height} alt={SCREENS[id].alt} loading="lazy" decoding="async" className="block h-auto w-full" />
        </picture>
      </div>
      <figcaption className="mt-4 t-subhead text-text-muted">{SCREENS[id].caption}</figcaption>
    </figure>
  );
}

/**
 * A row of phones: a swipeable strip on a phone (keyboard-focusable), a grid from 1024px. The screens are below the fold, so they load lazily.
 * Every list says once that the screens show sample data.
 */
export function ScreenList({ ids }: { ids: ReadonlyArray<ScreenId> }) {
  const n = Math.min(ids.length, 4) as 1 | 2 | 3 | 4;
  return (
    <div>
      <div role="region" aria-label="App screens" tabIndex={0} className="-mx-4 overflow-x-auto px-4 pb-2 [scroll-snap-type:x_mandatory] lg:mx-0 lg:overflow-visible lg:px-0 lg:pb-0">
        <ul data-stagger className={`flex w-max gap-6 lg:grid lg:w-auto lg:gap-8 ${COLUMNS[n]}`}>
          {ids.map((id) => (
            <li key={id} className="w-[240px] shrink-0 [scroll-snap-align:start] lg:w-auto">
              <Phone id={id} />
            </li>
          ))}
        </ul>
      </div>
      <p className="mt-6 t-subhead text-text-subtle">The screens show sample data, not real people or startups.</p>
    </div>
  );
}

/** A section of its own: heading, one sentence, then the phones. */
export function ScreenTour({ heading, lede, ids }: { heading: string; lede: string; ids: ReadonlyArray<ScreenId> }) {
  return (
    <section aria-labelledby="tour-h">
      <Container className="pb-20 lg:pb-[120px]">
        <h2 id="tour-h" className="t-title1">{heading}</h2>
        <p className="mt-3 max-w-[540px] t-body text-text-muted">{lede}</p>
        <div className="mt-8"><ScreenList ids={ids} /></div>
      </Container>
    </section>
  );
}
