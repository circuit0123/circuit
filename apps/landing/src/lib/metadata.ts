import type { Metadata } from "next";
import type { AudiencePageContent } from "@/content/types";

/**
 * Per-page metadata. A page's `openGraph` / `twitter` replaces the layout's whole object (Next merges one level deep), so the image
 * and site details are repeated here: every page shares the on-dark logo on black (`/og.png`, 1200×630).
 */
export function pageMetadata(p: AudiencePageContent): Metadata {
  const url = `/${p.slug}/`;
  return {
    title: p.title,
    description: p.description,
    alternates: { canonical: url },
    openGraph: {
      type: "website",
      siteName: "Circuit",
      locale: "en_IN",
      url,
      title: p.title,
      description: p.description,
      images: [{ url: "/og.png", width: 1200, height: 630, alt: "Circuit" }],
    },
    twitter: { card: "summary_large_image", title: p.title, description: p.description, images: ["/og.png"] },
  };
}
