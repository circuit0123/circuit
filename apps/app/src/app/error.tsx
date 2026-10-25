"use client";

import { ServerError } from "@/components/ServerError";

/** A screen threw while rendering. The rest of the app (the providers, the bar) is still standing, so this fills the page. */
export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <ServerError reset={reset} />;
}
