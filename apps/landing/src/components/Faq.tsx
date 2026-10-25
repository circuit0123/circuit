import { FAQ } from "@/content/home";
import { Container } from "./Container";

/** Plain <details>: works without JavaScript and with a keyboard. */
export function Faq() {
  return (
    <section aria-labelledby="faq-h">
      <Container narrow className="pb-20 lg:pb-[120px]">
        <h2 id="faq-h" className="t-title1 mb-4">Questions</h2>
        {FAQ.map((f) => (
          <details key={f.q} className="group border-b border-separator py-1">
            <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 py-3 t-body font-medium [&::-webkit-details-marker]:hidden">
              {f.q}
              <span aria-hidden="true" className="text-text-subtle transition-transform group-open:rotate-45">+</span>
            </summary>
            <p className="max-w-[540px] pb-4 t-body text-text-muted">{f.a}</p>
          </details>
        ))}
      </Container>
    </section>
  );
}
