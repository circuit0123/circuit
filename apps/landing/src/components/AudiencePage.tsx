import { INVITE_ONLY } from "@/content/home";
import { page } from "@/content/pages";
import type { Slug } from "@/content/types";
import { JOIN_LIVE, WAITLIST_MODE } from "@/lib/env";
import { flagOn, getFeatures } from "@/lib/features";
import { CtaLink } from "./CtaLink";
import { Container } from "./Container";
import { Faq } from "./Faq";
import { Footer } from "./Footer";
import { Header } from "./Header";
import { Hero } from "./Hero";
import { FoundersProof } from "./proof/FoundersProof";
import { InvestorsProof } from "./proof/InvestorsProof";
import { MentorsProof } from "./proof/MentorsProof";
import { PartnersProof } from "./proof/PartnersProof";
import { StudentsProof } from "./proof/StudentsProof";
import { PartnerForm } from "./PartnerForm";
import { ScreenTour } from "./Screens";
import { Waitlist } from "./Waitlist";

/** The proof section of each page: a labelled example or a labelled placeholder, never invented numbers or people. */
const PROOF: Partial<Record<Slug, React.ReactNode>> = {
  students: <StudentsProof />,
  founders: <FoundersProof />,
  mentors: <MentorsProof />,
  investors: <InvestorsProof />,
  partners: <PartnersProof />,
};

/** Extra screens that sit between the hero and the proof. Students, investors and partners show theirs inside their proof section instead. */
const TOUR: Partial<Record<Slug, React.ReactNode>> = {
  founders: <ScreenTour heading="What founders see" lede="A match with the reason, people near you, and the conversation that turns it into an introduction." ids={[{ id: "home-match", caption: "Every match says why, and shows the mutual connection who can introduce you. A Bridge badge marks a match across sectors." }, "people", "inbox"]} />,
  mentors: <ScreenTour heading="What mentors see" lede="People who need what you know, circuits that need your yes, and the conversation that starts it." ids={[{ id: "people", caption: "Each introduction shows the reason before you decide anything." }, { id: "circuits", caption: "Circuits: three people, each helping the next. Nothing starts without your yes." }, "chat"]} />,
};

const closing = "inline-flex min-h-11 items-center t-body font-medium underline underline-offset-4";

/**
 * Header → hero → three steps → one proof section → (a form, see below) → FAQ → closing link → footer.
 * What the call to action does depends on two build-time settings:
 * - NEXT_PUBLIC_JOIN_LIVE off (the app has no /join yet): the button keeps its label but jumps to a waitlist form on this page (role fixed to the
 *   page's audience), or to the contact form on /partners.
 * - Feature flags from /api/config: with `investor_mode` off there is no investor role in the app, so /investors shows the waitlist form
 *   (role=investor) where the button would be, plus "Investor access opens soon." With `partner_mode` off, /partners shows the contact form.
 */
export async function AudiencePage({ slug }: { slug: Slug }) {
  const p = page(slug);
  const features = await getFeatures();
  const src = `landing-${slug}`;
  const waitlistOnly = !WAITLIST_MODE && slug === "investors" && !flagOn(features, "investor_mode");
  const contactOnly = slug === "partners" && (WAITLIST_MODE || !flagOn(features, "partner_mode") || !JOIN_LIVE);
  const waitlistSection = (WAITLIST_MODE || !JOIN_LIVE) && !waitlistOnly && slug !== "partners";
  const formId = contactOnly ? "partner-form" : "waitlist";

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
            ) : (
              <CtaLink button="primary" src={src} role={p.role} form={formId} toForm={contactOnly}>{p.cta}</CtaLink>
            )
          }
        />
        {TOUR[slug]}
        {PROOF[slug]}
        {contactOnly ? <PartnerForm intro={JOIN_LIVE ? undefined : INVITE_ONLY.heading + "."} /> : null}
        {waitlistSection ? <Waitlist src={src} role={p.role} heading={INVITE_ONLY.heading} copy={INVITE_ONLY.copy} /> : null}
        <Faq items={p.faq} />
        <section aria-label="Next step">
          <Container className="pb-20 lg:pb-[120px]">
            {waitlistOnly ? (
              <a href="#waitlist" className={closing}>Join the waitlist <span aria-hidden="true">&nbsp;→</span></a>
            ) : (
              <CtaLink src={src} role={p.role} form={formId} toForm={contactOnly} className={closing}>{p.cta} <span aria-hidden="true">&nbsp;→</span></CtaLink>
            )}
          </Container>
        </section>
      </main>
      <Footer />
    </>
  );
}
