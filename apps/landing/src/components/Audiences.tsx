import { AUDIENCES, SRC } from "@/content/home";
import { joinUrl } from "@/lib/env";
import { Container } from "./Container";

/** Five tiles, one per audience. Each links straight into the app with that role pre-set. */
export function Audiences() {
  return (
    <section aria-labelledby="audiences-h">
      <Container className="pb-20 lg:pb-[120px]">
        <h2 id="audiences-h" className="t-title1 mb-6">Who it&rsquo;s for</h2>
        <ul className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4">
          {AUDIENCES.map((a) => (
            <li key={a.id} className="contents">
              <a
                id={a.id}
                href={joinUrl(SRC, a.role)}
                data-press
                className="flex min-h-[180px] scroll-mt-4 flex-col justify-between gap-6 rounded-card bg-surface p-surface"
              >
                <span>
                  <span className="block t-headline">{a.who}</span>
                  <span className="mt-2 block t-subhead text-text-muted">{a.line}</span>
                </span>
                <span className="t-subhead">{a.cta} <span aria-hidden="true">→</span></span>
              </a>
            </li>
          ))}
        </ul>
      </Container>
    </section>
  );
}
