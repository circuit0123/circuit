import { Audiences } from "@/components/Audiences";
import { CtaLink } from "@/components/CtaLink";
import { Faq } from "@/components/Faq";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { HeroVideo } from "@/components/HeroVideo";
import { ScreenTour } from "@/components/Screens";
import { PilotCity } from "@/components/PilotCity";
import { Waitlist } from "@/components/Waitlist";
import { FAQ, INVITE_ONLY, SRC } from "@/content/home";
import { JOIN_LIVE } from "@/lib/env";
import { flagOn, getFeatures } from "@/lib/features";

export default async function Page() {
  const features = await getFeatures();
  return (
    <>
      <Header />
      <main id="main">
        <Hero
          size="display"
          headline="Build with people near you."
          subhead="Circuit matches you on what you need and what you can offer, not on your college name or job title."
          action={<CtaLink button="primary" src={SRC}>Join the beta</CtaLink>}
          media={<HeroVideo />}
        />
        <Audiences investorOpen={flagOn(features, "investor_mode")} />
        <ScreenTour heading="A look inside" lede="Matches with a reason, jobs and startups on a map, and circuits where three people help each other." ids={[
          { id: "home-main", caption: "Today: three matches a day. Each comes with the reason and the mutual connection who can introduce you." },
          "discover-jobs",
          "map",
          { id: "circuits", caption: "Circuits: warm intros and three-way loops where everyone helps someone." },
        ]} />
        {/* Hidden until real counts exist: no public stats endpoint yet, so nothing is passed (never fake numbers). */}
        <PilotCity stats={null} />
        {JOIN_LIVE ? (
          <Waitlist
            src={SRC}
            copy="We are opening Circuit one city and one college at a time. Leave your email and we’ll write when there’s a place for you."
          />
        ) : (
          <Waitlist src={SRC} heading={INVITE_ONLY.heading} copy={INVITE_ONLY.copy} />
        )}
        <Faq items={FAQ} />
      </main>
      <Footer />
    </>
  );
}
