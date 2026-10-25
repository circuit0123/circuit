import { notFound } from "next/navigation";
import { Gallery } from "@/components/design/Gallery";
import { APP_ENV } from "@/lib/env";

export const metadata = { title: "Circuit — design" };

/** Dev only: every packages/ui component in every state, in both themes (CLAUDE.md: Frontend architecture). */
export default function DesignPage() {
  if (APP_ENV !== "dev") notFound();
  return <Gallery />;
}
