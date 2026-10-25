import type { Step } from "@/content/types";
import { Container } from "./Container";
import { Shot } from "./Shot";

export function HowItWorks({ steps }: { steps: ReadonlyArray<Step> }) {
  return (
    <section aria-labelledby="how-h">
      <Container className="pb-20 lg:pb-[120px]">
        <h2 id="how-h" className="t-title1 mb-6">How it works</h2>
        <ol className="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-8">
          {steps.map((s) => (
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
