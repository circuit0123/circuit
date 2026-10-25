import { page } from "@/content/pages";
import type { Slug } from "@/content/types";
import { CtaLink } from "./CtaLink";
import { Container } from "./Container";
import { Faq } from "./Faq";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { FoundersProof } from "./proof/FoundersProof";
import { MentorsProof } from "./proof/MentorsProof";
import { StudentsProof } from "./proof/StudentsProof";

/** The proof section of each page: a labelled example or a labelled placeholder, never invented numbers or people. */
const PROOF: Partial<Record<Slug, React.ReactNode>> = {
  students: <StudentsProof />,
  founders: <FoundersProof />,
  mentors: <MentorsProof />,
};

/** Header → hero → three steps → one proof section → FAQ → closing link → footer. */
export function AudiencePage({ slug }: { slug: Slug }) {
  const p = page(slug);
  const src = `landing-${slug}`;
  return (
    <>
      <Header current={slug} />
      <main id="main">
        <Hero
          headline={p.headline}
          subhead={p.subhead}
          action={<CtaLink button="primary" src={src} role={p.role}>{p.cta}</CtaLink>}
        />
        <HowItWorks steps={p.steps} />
        {PROOF[slug]}
        <Faq items={p.faq} />
        <section aria-label="Next step">
          <Container className="pb-20 lg:pb-[120px]">
            <CtaLink src={src} role={p.role} className="inline-flex min-h-11 items-center t-body font-medium underline underline-offset-4">{p.cta} <span aria-hidden="true">&nbsp;→</span></CtaLink>
          </Container>
        </section>
      </main>
      <Footer />
    </>
  );
}
