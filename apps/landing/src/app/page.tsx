import { Audiences } from "@/components/Audiences";
import { Faq } from "@/components/Faq";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";
import { Hero } from "@/components/Hero";
import { HowItWorks } from "@/components/HowItWorks";
import { PilotCity } from "@/components/PilotCity";
import { Waitlist } from "@/components/Waitlist";

export default function Page() {
  return (
    <>
      <Header />
      <main id="main">
        <Hero />
        <Audiences />
        <HowItWorks />
        {/* Hidden until real counts exist: no public stats endpoint yet, so nothing is passed (never fake numbers). */}
        <PilotCity stats={null} />
        <Waitlist />
        <Faq />
      </main>
      <Footer />
    </>
  );
}
