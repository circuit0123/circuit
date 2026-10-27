import type { Role } from "@/lib/env";

export type FaqItem = { q: string; a: string };

export const SLUGS = ["students", "founders", "mentors", "investors", "partners"] as const;
export type Slug = (typeof SLUGS)[number];

/** One audience page (DESIGN.md §4 "Landing site"). Headline and call to action come from the table there. */
export type AudiencePageContent = {
  slug: Slug;
  role: Role;
  /** Short name used in the header and tiles. */
  who: string;
  /** Browser title and Open Graph title (the layout adds " — Circuit"). */
  title: string;
  description: string;
  headline: string;
  subhead: string;
  cta: string;
  /** 4 to 6 honest answers for this audience. */
  faq: FaqItem[];
};
