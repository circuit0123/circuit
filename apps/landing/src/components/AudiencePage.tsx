import { page } from "@/content/pages";
import type { Slug } from "@/content/types";
import { flagOn, getFeatures } from "@/lib/features";
import { CtaLink } from "./CtaLink";
import { Container } from "./Container";
import { Faq } from "./Faq";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { FoundersProof } from "./proof/FoundersProof";
import { InvestorsProof } from "./proof/InvestorsProof";
import { LinkButton } from "@circuit/ui/Button";
import { MentorsProof } from "./proof/MentorsProof";
import { PartnersProof } from "./proof/PartnersProof";
import { StudentsProof } from "./proof/StudentsProof";
import { PartnerForm } from "./PartnerForm";
import { Waitlist } from "./Waitlist";

/** The proof section of each page: a labelled example or a labelled placeholder, never invented numbers or people. */
const PROOF: Partial<Record<Slug, React.ReactNode>> = {
  students: <StudentsProof />,
  founders: <FoundersProof />,
  mentors: <MentorsProof />,
  investors: <InvestorsProof />,
  partners: <PartnersProof />,
};

const closing = "inline-flex min-h-11 items-center t-body font-medium underline underline-offset-4";

/**
 * Header → hero → three steps → one proof section → FAQ → closing link → footer.
 * Feature flags are read at build time. With `investor_mode` off there is no investor role in the app, so /investors shows the waitlist
 * form (role=investor) where the app button would be, plus "Investor access opens soon." With `partner_mode` off, /partners keeps the same
 * button text but it jumps to a short contact form (role=partner) below the proof section instead of opening the app.
 */
export async function AudiencePage({ slug }: { slug: Slug }) {
  const p = page(slug);
  const features = await getFeatures();
  const src = `landing-${slug}`;
  const waitlistOnly = slug === "investors" && !flagOn(features, "investor_mode");
  const contactOnly = slug === "partners" && !flagOn(features, "partner_mode");

  return (
    <>
      <Header current={slug} />
      <main id="main">
        <Hero
          headline={p.headline}
          subhead={p.subhead}
          action={
            waitlistOnly ? (
              <div>
                <p className="mb-4 t-body font-medium">Investor access opens soon.</p>
                <Waitlist layout="inline" src={src} role="investor" />
              </div>
            ) : contactOnly ? (
              <LinkButton variant="primary" href="#partner-form">{p.cta}</LinkButton>
            ) : (
              <CtaLink button="primary" src={src} role={p.role}>{p.cta}</CtaLink>
            )
          }
        />
        <HowItWorks steps={p.steps} />
        {PROOF[slug]}
        {contactOnly ? <PartnerForm /> : null}
        <Faq items={p.faq} />
        <section aria-label="Next step">
          <Container className="pb-20 lg:pb-[120px]">
            {waitlistOnly ? (
              <a href="#waitlist" className={closing}>Join the waitlist <span aria-hidden="true">&nbsp;→</span></a>
            ) : contactOnly ? (
              <a href="#partner-form" className={closing}>{p.cta} <span aria-hidden="true">&nbsp;→</span></a>
            ) : (
              <CtaLink src={src} role={p.role} className={closing}>{p.cta} <span aria-hidden="true">&nbsp;→</span></CtaLink>
            )}
          </Container>
        </section>
      </main>
      <Footer />
    </>
  );
}
