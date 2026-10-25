import Link from "next/link";
import { AUDIENCES, SRC } from "@/content/home";
import { CtaLink } from "./CtaLink";
import { Container } from "./Container";

const tile = "flex min-h-[180px] scroll-mt-4 flex-col justify-between gap-6 rounded-card bg-surface p-surface";

/**
 * Five tiles, one per audience. Each links straight into the app with that role pre-set.
 * Exception: while `investor_mode` is off the app has no investor role, so that tile opens the /investors page (its waitlist) instead.
 */
export function Audiences({ investorOpen }: { investorOpen: boolean }) {
  return (
    <section aria-labelledby="audiences-h">
      <Container className="pb-20 lg:pb-[120px]">
        <h2 id="audiences-h" className="t-title1 mb-6">Who it&rsquo;s for</h2>
        <ul className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
          {AUDIENCES.map((a) => {
            const body = (
              <>
                <span>
                  <span className="block t-headline">{a.who}</span>
                  <span className="mt-2 block t-subhead text-text-muted">{a.line}</span>
                </span>
                <span className="t-subhead">{a.cta} <span aria-hidden="true">→</span></span>
              </>
            );
            return (
              <li key={a.id} className="contents">
                {a.role === "investor" && !investorOpen ? (
                  <Link id={a.id} prefetch={false} href="/investors/" data-press className={tile}>{body}</Link>
                ) : (
                  <CtaLink id={a.id} src={SRC} role={a.role} data-press className={tile}>{body}</CtaLink>
                )}
              </li>
            );
          })}
        </ul>
      </Container>
    </section>
  );
}
