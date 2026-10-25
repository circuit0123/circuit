import type { FaqItem } from "@/content/types";
import { Container } from "./Container";

/** Plain <details>: works without JavaScript and with a keyboard. LandingMotion adds the fade-and-rise (the `data-faq*` hooks). */
export function Faq({ items }: { items: ReadonlyArray<FaqItem> }) {
  return (
    <section aria-labelledby="faq-h">
      <Container narrow className="pb-20 lg:pb-[120px]">
        <h2 id="faq-h" className="t-title1 mb-4">Questions</h2>
        {items.map((f) => (
          <details key={f.q} data-faq className="group border-b border-separator py-1">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 py-3 t-body font-medium [&::-webkit-details-marker]:hidden">
              {f.q}
              <span aria-hidden="true" data-faq-plus className="text-text-subtle transition-transform duration-[350ms] ease-[cubic-bezier(0.22,1,0.36,1)] group-open:rotate-45 motion-reduce:transition-none">+</span>
            </summary>
            <p data-faq-answer className="max-w-[540px] pb-4 t-body text-text-muted">{f.a}</p>
          </details>
        ))}
      </Container>
    </section>
  );
}
