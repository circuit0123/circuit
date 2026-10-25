"use client";

import { Button, Logo } from "@circuit/ui";

/** The 500 screen: what happened and what to do (DESIGN.md §9). Used by the route error boundary and the global one. */
export function ServerError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col justify-center gap-12 lg:gap-16 px-4 py-12 pt-[max(48px,env(safe-area-inset-top))]">
      <Logo kind="mark" height={32} />
      <div className="flex flex-col gap-2">
        <h1 className="t-title1">Something went wrong on our side</h1>
        <p className="t-body text-text-muted">We're looking into it. Try again in a moment.</p>
      </div>
      <Button variant="primary" className="w-full" onClick={reset}>Try again</Button>
      {/* A plain link on purpose: this also renders when the router itself is what failed, and a full load is the reset we want. */}
      {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
      <a href="/" className="t-body self-start underline">Go to Home</a>
    </main>
  );
}
