import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { HomeV2 } from "@/components/v2/HomeV2";
import { flagOn, getFeatures } from "@/lib/features";
import { UI_V2_MODE } from "@/lib/uiV2";

// The preview of the v2 home: hidden from search engines and the sitemap. With NEXT_PUBLIC_UI_V2 off the route does not exist.
export const metadata: Metadata = { robots: { index: false, follow: false }, alternates: { canonical: "/" } };

export default async function Page() {
  if (UI_V2_MODE === "off") notFound();
  const features = await getFeatures();
  return (
    <>
      <script dangerouslySetInnerHTML={{ __html: 'document.documentElement.dataset.ui="v2"' }} />
      <HomeV2 investorOpen={flagOn(features, "investor_mode")} />
    </>
  );
}
