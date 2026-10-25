import { STEPS } from "@/content/home";
import { Container } from "./Container";

/** A real app screenshot (dark and light versions, AVIF with a WebP fallback), or a clearly labelled frame when that screen isn't built yet. */
function Shot({ step }: { step: (typeof STEPS)[number] }) {
  const frame = "relative aspect-[39/64] overflow-hidden rounded-sheet bg-surface";
  if (!step.shot) {
    return (
      <div role="img" aria-label={`App screenshot coming: ${step.missing} screen`} className={`${frame} flex items-center justify-center p-6 text-center t-subhead text-text-subtle`}>
        App screenshot coming: {step.missing}
      </div>
    );
  }
  const s = `/shots/${step.shot}`;
  return (
    <div className={frame}>
      <picture>
        <source media="(prefers-color-scheme: light)" srcSet={`${s}-light.avif`} type="image/avif" />
        <source media="(prefers-color-scheme: light)" srcSet={`${s}-light.webp`} type="image/webp" />
        <source srcSet={`${s}-dark.avif`} type="image/avif" />
        <img src={`${s}-dark.webp`} width={780} height={1280} alt={step.alt} loading="lazy" decoding="async" className="h-full w-full object-cover object-top" />
      </picture>
    </div>
  );
}

export function HowItWorks() {
  return (
    <section aria-labelledby="how-h">
      <Container className="pb-20 lg:pb-[120px]">
        <h2 id="how-h" className="t-title1 mb-6">How it works</h2>
        <ol className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-8">
          {STEPS.map((s) => (
            <li key={s.n}>
              <Shot step={s} />
              <p className="mt-5 t-subhead tabular-nums text-text-subtle">{s.n}</p>
              <h3 className="mt-1 t-title2">{s.title}</h3>
              <p className="mt-2 t-body text-text-muted">{s.body}</p>
            </li>
          ))}
        </ol>
      </Container>
    </section>
  );
}
