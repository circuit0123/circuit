import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Privacy", robots: { index: false }, alternates: { canonical: "/privacy/" } };

export default function Page() {
  return <LegalPage title="Privacy" />;
}
