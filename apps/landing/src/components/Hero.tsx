import { LinkButton } from "@circuit/ui/Button";
import { SRC } from "@/content/home";
import { joinUrl } from "@/lib/env";
import { Container } from "./Container";
import { HeroVideo } from "./HeroVideo";

/** One headline, one subhead, ONE primary button. The video sits beside the headline on desktop and under the button on a phone. */
export function Hero() {
  return (
    <section aria-label="Introduction">
      <Container className="grid items-center gap-12 pb-20 pt-12 lg:grid-cols-[1fr_auto] lg:gap-16 lg:pb-[96px] lg:pt-[96px]">
        <div>
          <h1 className="t-display max-w-[820px] text-balance">Build with people near you.</h1>
          <p className="mt-6 max-w-[560px] t-lede text-text-muted">
            Circuit matches you on what you need and what you can offer, not on your college name or job title.
          </p>
          <LinkButton variant="primary" href={joinUrl(SRC)} className="mt-10">Join the beta</LinkButton>
        </div>
        <HeroVideo />
      </Container>
    </section>
  );
}
