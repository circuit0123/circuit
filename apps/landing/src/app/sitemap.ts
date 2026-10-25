import type { MetadataRoute } from "next";
import { LANDING_URL } from "@/lib/env";

export const dynamic = "force-static";

/** Public pages worth indexing. The audience pages join this list next session; the legal holding pages stay out. */
export default function sitemap(): MetadataRoute.Sitemap {
  return [{ url: `${LANDING_URL}/`, changeFrequency: "monthly", priority: 1 }];
}
