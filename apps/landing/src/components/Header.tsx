import Link from "next/link";
import { Logo } from "@circuit/ui/Logo";
import { AUDIENCES } from "@/content/home";
import { Container } from "./Container";

/** Logo and the five audience links. Until the audience pages exist (next session) they jump to the tiles on the home page. */
export function Header() {
  return (
    <header>
      <Container className="flex flex-wrap items-center justify-between gap-x-4 py-3 lg:py-5">
        <Link prefetch={false} href="/" aria-label="Circuit home" className="inline-flex min-h-11 items-center">
          <Logo kind="lockup" height={28} />
        </Link>
        <nav aria-label="Audiences" className="-mx-3 flex flex-wrap lg:mx-0">
          {AUDIENCES.map((a) => (
            <Link key={a.id} href={`/#${a.id}`} className="inline-flex min-h-11 items-center px-3 t-subhead text-text-muted hover:text-text lg:px-3">
              {a.who}
            </Link>
          ))}
        </nav>
      </Container>
    </header>
  );
}
