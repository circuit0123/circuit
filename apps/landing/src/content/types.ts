import type { Role } from "@/lib/env";
import type { ScreenId } from "./screens";

/** `screen` (a picture from public/screens) wins over `shot`. `shot` is the file in public/shots (without extension); null = the screen doesn't exist in the app yet, so a labelled placeholder is shown. */
export type Step = { n: string; title: string; body: string; shot: string | null; alt: string; missing: string; screen?: ScreenId };
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
  steps: [Step, Step, Step];
  /** 4 to 6 honest answers for this audience. */
  faq: FaqItem[];
};
