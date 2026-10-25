import type { Metadata } from "next";
import { LegalPage } from "@/components/LegalPage";

export const metadata: Metadata = { title: "Terms", robots: { index: false }, alternates: { canonical: "/terms/" } };

export default function Page() {
  return <LegalPage title="Terms" />;
}
