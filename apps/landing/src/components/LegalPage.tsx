import { Container } from "./Container";
import { Footer } from "./Footer";
import { Header } from "./Header";

/** Holding page for a legal document until the lawyer-approved text is published (docs/legal holds drafts only). */
export function LegalPage({ title }: { title: string }) {
  return (
    <>
      <Header />
      <main id="main">
        <Container narrow className="pb-20 pt-12 lg:pb-[120px] lg:pt-[96px]">
          <h1 className="t-title1">{title}</h1>
          <p className="mt-4 max-w-[540px] t-body text-text-muted">
            We are finishing this document with our lawyer. It will be published here before the beta opens. Until then, you can write to us with any question about your data.
          </p>
        </Container>
      </main>
      <Footer />
    </>
  );
}
