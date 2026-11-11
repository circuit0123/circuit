import Link from "next/link";
import { BigHeadline, EmeraldBand, LogoV2, MonoLabel } from "@circuit/ui/v2";
import { AUDIENCES, FAQ_V2, INVITE_ONLY, SRC, STEPS_V2 } from "@/content/home";
import { COMPANY_LEGAL_NAME, CONTACT_EMAIL, JOIN_LIVE } from "@/lib/env";
import { CtaLink } from "../CtaLink";
import { Waitlist } from "../Waitlist";

const wrap = "mx-auto w-full max-w-[1200px] px-6";
const h2 = "m-0 text-[clamp(44px,6vw,80px)] font-bold leading-[0.95] tracking-[-0.055em]";
const Dot = () => <span className="text-c-bright">.</span>;
const stepStyle = [
  "bg-c-hero text-c-hero-text border-[#3a3a3a]",
  "bg-c-card text-c-text border-c-border",
  "bg-c-brand text-c-text border-c-brand",
];

/**
 * The v2 landing home (PMLanding.dc.html). Server component; the one loud moment is the hero. Left out on purpose: the sample intro card,
 * the "Strong match" pill, the vouch quote, the "three a day" claim and "no cold messages" (docs/ui-v2-plan.md §5).
 */
export function HomeV2({ investorOpen }: { investorOpen: boolean }) {
  const tiles = AUDIENCES.filter((a) => a.role !== "investor" || investorOpen);
  return (
    <div className="overflow-hidden bg-c-bg text-c-text">
      <header className={`${wrap} relative z-[2] flex flex-wrap items-center justify-between gap-4 py-[22px]`}>
        <Link prefetch={false} href="/" aria-label="Circuit home" className="inline-flex min-h-11 items-center"><LogoV2 height={27} /></Link>
        <nav aria-label="Main" className="flex flex-wrap gap-x-7 text-[15px] text-c-muted">
          <a href="#how" className="inline-flex min-h-11 items-center hover:text-c-bright">How it works</a>
          <a href="#who" className="inline-flex min-h-11 items-center hover:text-c-bright">Who it&rsquo;s for</a>
          <a href="#faq" className="inline-flex min-h-11 items-center hover:text-c-bright">FAQ</a>
        </nav>
        <CtaLink src={SRC} className="inline-flex h-11 items-center rounded-xl bg-c-bright px-[18px] text-[15px] font-semibold text-c-bg">Join the beta</CtaLink>
      </header>

      <main id="main">
        <section aria-label="Introduction" className="relative">
          <EmeraldBand className="-left-[10%] top-[180px] h-[150px] w-[120%]" rotate={-5} />
          <div className={`${wrap} relative pb-28 pt-12`}>
            <MonoLabel className="text-[13px]">Invite-only beta</MonoLabel>
            <BigHeadline size="landing" first="Build with people" second="near you." className="mt-[18px]" />
            <p className="mt-7 max-w-[520px] text-[20px] leading-[1.5] text-[#c2c4c9]">Circuit matches you on what you need and what you can offer, not on your college name or job title.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <CtaLink src={SRC} className="inline-flex h-[54px] items-center rounded-[14px] bg-c-bright px-[26px] text-[17px] font-semibold text-c-bg">Join the beta</CtaLink>
              <a href="#how" className="inline-flex h-[54px] items-center rounded-[14px] border border-c-border bg-c-card px-6 text-[17px] font-medium">See how it works</a>
            </div>
          </div>
        </section>

        <section id="how" aria-labelledby="how-h" className={`${wrap} py-24`}>
          <h2 id="how-h" className={`${h2} mb-10`}>How it works<Dot /></h2>
          <ol className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-4 p-0">
            {STEPS_V2.map((s, i) => (
              <li key={s.n} className={`flex min-h-[240px] flex-col justify-between rounded-[22px] border p-[26px] ${stepStyle[i]}`}>
                <span className="font-mono text-[13px] text-c-bright">{s.n}</span>
                <span>
                  <span className="block text-[24px] font-bold tracking-[-0.035em]">{s.title}</span>
                  <span className="mt-2 block text-[16px] leading-[1.5] opacity-80">{s.body}</span>
                </span>
              </li>
            ))}
          </ol>
        </section>

        <section id="who" aria-labelledby="who-h" className="border-y border-[#1f2024]">
          <div className={`${wrap} py-24`}>
            <h2 id="who-h" className={`${h2} mb-8`}>Who it&rsquo;s for<Dot /></h2>
            <ul className="m-0 grid list-none grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-3 p-0">
              {tiles.map((a) => (
                <li key={a.id} className="contents">
                  <CtaLink id={a.id} src={SRC} role={a.role} className="flex min-h-[200px] flex-col justify-between gap-7 rounded-[18px] border border-c-border bg-c-card p-[22px]">
                    <span>
                      <span className="block text-[22px] font-bold tracking-[-0.03em]">{a.who}</span>
                      <span className="mt-2 block text-[15px] leading-[1.5] text-c-muted">{a.line}</span>
                    </span>
                    <span className="text-[15px] font-semibold text-c-bright">{a.cta} <span aria-hidden>→</span></span>
                  </CtaLink>
                </li>
              ))}
            </ul>
          </div>
        </section>

        <div className="[&_section]:text-c-text">
          {JOIN_LIVE
            ? <Waitlist src={SRC} copy="We are opening Circuit one city and one college at a time. Leave your email and we’ll write when there’s a place for you." />
            : <Waitlist src={SRC} heading={INVITE_ONLY.heading} copy={INVITE_ONLY.copy} />}
        </div>

        <section id="faq" aria-labelledby="faq-h" className={`${wrap} py-24`}>
          <div className="flex flex-wrap gap-12">
            <h2 id="faq-h" className={`${h2} min-w-[280px] flex-[1_1_280px]`}>Questions<Dot /></h2>
            <div className="min-w-0 flex-[2_1_460px]">
              {FAQ_V2.map((f) => (
                <details key={f.q} className="group border-b border-c-border py-5">
                  <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-4 text-[18px] font-semibold [&::-webkit-details-marker]:hidden">
                    {f.q}
                    <span aria-hidden className="text-c-bright transition-transform group-open:rotate-45 motion-reduce:transition-none">+</span>
                  </summary>
                  <p className="mt-3 text-[16px] leading-[1.55] text-c-muted">{f.a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-c-border bg-c-card">
        <div className={`${wrap} pb-10 pt-16`}>
          <div className="text-[clamp(56px,10vw,150px)] font-bold leading-[0.9] tracking-[-0.065em]">
            Come<br /><span style={{ color: "transparent", WebkitTextStroke: "2px var(--c-bright)" }}>build.</span>
          </div>
          <div className="mt-12 flex flex-wrap justify-between gap-6 border-t border-c-border pt-6 text-[14px] text-c-muted">
            <span>Circuit{COMPANY_LEGAL_NAME ? ` · ${COMPANY_LEGAL_NAME}` : ""}</span>
            <nav aria-label="Legal" className="flex gap-6">
              <Link prefetch={false} href="/privacy/" className="inline-flex min-h-11 items-center hover:text-c-bright">Privacy</Link>
              <Link prefetch={false} href="/terms/" className="inline-flex min-h-11 items-center hover:text-c-bright">Terms</Link>
              {CONTACT_EMAIL ? <a href={`mailto:${CONTACT_EMAIL}`} className="inline-flex min-h-11 items-center hover:text-c-bright">Contact</a> : null}
            </nav>
          </div>
        </div>
      </footer>
    </div>
  );
}
