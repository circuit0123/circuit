"use client";

import { notFound } from "next/navigation";
import { LANDING_URL } from "@/lib/env";
import { useSettings } from "@/data";
import { SettingsScreen } from "./SettingsHome";

export const LEGAL_DOCS = {
  privacy: { title: "Privacy policy", path: "/privacy" },
  terms: { title: "Terms", path: "/terms" },
  guidelines: { title: "Community guidelines", path: null },
} as const;
export type LegalDoc = keyof typeof LEGAL_DOCS;

/**
 * Legal pages. The texts are drafts with our lawyer (docs/legal), so, like the landing site, this says so plainly until the approved
 * text is published; then it links to it. The version the member accepted is shown.
 */
export function LegalScreen({ doc }: { doc: string }) {
  const s = useSettings();
  if (!(doc in LEGAL_DOCS)) notFound();
  const d = LEGAL_DOCS[doc as LegalDoc];
  return (
    <SettingsScreen title={d.title} backLabel="Settings">
      <div className="flex max-w-[540px] flex-col gap-4 px-4 lg:px-0">
        <p className="t-body">We&apos;re finishing this document with our lawyer. It will be published here before the beta opens. Until then, you can write to us with any question about your data.</p>
        {s.summary && <p className="t-subhead text-text-muted">You accepted policy version {s.summary.policyVersion}.</p>}
        {LANDING_URL && d.path && <a href={`${LANDING_URL}${d.path}`} target="_blank" rel="noopener noreferrer" className="t-body underline">Read it on our website</a>}
      </div>
    </SettingsScreen>
  );
}
