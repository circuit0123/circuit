import Link from "next/link";
import { PAGES } from "@/content/pages";
import { COMPANY_LEGAL_NAME, CONTACT_EMAIL } from "@/lib/env";
import { Container } from "./Container";

const link = "inline-flex min-h-11 items-center px-3 text-text-muted hover:text-text";

export function Footer() {
  return (
    <footer className="border-t border-separator">
      <Container className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 pb-12 pt-8 t-subhead text-text-subtle">
        <span>Circuit{COMPANY_LEGAL_NAME ? ` · ${COMPANY_LEGAL_NAME}` : ""}</span>
        <div className="-mx-3 flex flex-wrap">
          <nav aria-label="Pages" className="flex flex-wrap">
            {PAGES.map((p) => <Link key={p.slug} prefetch={false} href={`/${p.slug}/`} className={link}>{p.who}</Link>)}
          </nav>
          <nav aria-label="Legal" className="flex flex-wrap">
            <Link prefetch={false} href="/privacy/" className={link}>Privacy</Link>
            <Link prefetch={false} href="/terms/" className={link}>Terms</Link>
            {CONTACT_EMAIL ? <a href={`mailto:${CONTACT_EMAIL}`} className={link}>Contact</a> : null}
          </nav>
        </div>
      </Container>
    </footer>
  );
}
