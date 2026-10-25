"use client";

import "./globals.css";
import { ServerError } from "@/components/ServerError";

/** The root layout itself failed, so there is no provider or font here: it brings its own <html> and the stylesheet. */
export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <html lang="en-IN">
      <body>
        <ServerError reset={reset} />
      </body>
    </html>
  );
}
