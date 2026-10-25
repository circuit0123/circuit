import { Container } from "../Container";

/** The shared frame of a proof section: one heading, one sentence, then the sample. */
export function Proof({ heading, lede, children }: { heading: string; lede: string; children: React.ReactNode }) {
  return (
    <section aria-labelledby="proof-h">
      <Container className="pb-20 lg:pb-[120px]">
        <h2 id="proof-h" className="t-title1">{heading}</h2>
        <p className="mt-3 max-w-[540px] t-body text-text-muted">{lede}</p>
        <div className="mt-8">{children}</div>
      </Container>
    </section>
  );
}
