import { LinkButton, Logo } from "@circuit/ui";

/**
 * The 404 screen (DESIGN.md §1a "the back of the fence"). Also what a deep link to a feature that is off shows (§3): from the outside
 * an off feature and a page that never existed look the same. Plain, one sentence, one way home.
 */
export function NotFound() {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col justify-center gap-12 lg:gap-16 px-4 py-12 pt-[max(48px,env(safe-area-inset-top))]">
      <Logo kind="mark" height={32} />
      <div className="flex flex-col gap-2">
        <h1 className="t-title1">We couldn't find that page</h1>
        <p className="t-body text-text-muted">It may have moved, or the link may be wrong. Home has what's new today.</p>
      </div>
      <LinkButton variant="primary" href="/" className="w-full">Go to Home</LinkButton>
    </main>
  );
}
