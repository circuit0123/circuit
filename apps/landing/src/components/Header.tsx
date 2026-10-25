import Link from "next/link";
import { Logo } from "@circuit/ui/Logo";
import { PAGES } from "@/content/pages";
import type { Slug } from "@/content/types";
import { Container } from "./Container";

/** Logo and the five audience pages. The page you are on is marked (`aria-current="page"`) and set in the full text colour. */
export function Header({ current }: { current?: Slug }) {
  return (
    <header>
      <Container className="flex flex-wrap items-center justify-between gap-x-4 py-3 lg:py-5">
        <Link prefetch={false} href="/" aria-label="Circuit home" className="inline-flex min-h-11 items-center">
          <Logo kind="lockup" height={28} />
        </Link>
        <nav aria-label="Audiences" className="-mx-3 flex flex-wrap lg:mx-0">
          {PAGES.map((p) => (
            <Link
              key={p.slug}
              prefetch={false}
              href={`/${p.slug}/`}
              aria-current={p.slug === current ? "page" : undefined}
              className={`inline-flex min-h-11 items-center px-3 t-subhead hover:text-text ${p.slug === current ? "font-medium text-text" : "text-text-muted"}`}
            >
              {p.who}
            </Link>
          ))}
        </nav>
      </Container>
    </header>
  );
}
