import Link from "next/link";
import { COMPANY_LEGAL_NAME, CONTACT_EMAIL } from "@/lib/env";
import { Container } from "./Container";

export function Footer() {
  return (
    <footer className="border-t border-separator">
      <Container className="flex flex-wrap items-center justify-between gap-x-6 gap-y-2 pb-12 pt-8 t-subhead text-text-subtle">
        <span>Circuit{COMPANY_LEGAL_NAME ? ` · ${COMPANY_LEGAL_NAME}` : ""}</span>
        <nav aria-label="Legal" className="-mx-3 flex flex-wrap">
          <Link prefetch={false} href="/privacy" className="inline-flex min-h-11 items-center px-3 text-text-muted hover:text-text">Privacy</Link>
          <Link prefetch={false} href="/terms" className="inline-flex min-h-11 items-center px-3 text-text-muted hover:text-text">Terms</Link>
          {CONTACT_EMAIL ? <a href={`mailto:${CONTACT_EMAIL}`} className="inline-flex min-h-11 items-center px-3 text-text-muted hover:text-text">Contact</a> : null}
        </nav>
      </Container>
    </footer>
  );
}
