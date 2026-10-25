import type { MetadataRoute } from "next";
import { PAGES } from "@/content/pages";
import { LANDING_URL } from "@/lib/env";

export const dynamic = "force-static";

/** Public pages worth indexing. The legal holding pages stay out. */
export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: `${LANDING_URL}/`, changeFrequency: "monthly", priority: 1 },
    ...PAGES.map((p) => ({ url: `${LANDING_URL}/${p.slug}/`, changeFrequency: "monthly" as const, priority: 0.8 })),
  ];
}
