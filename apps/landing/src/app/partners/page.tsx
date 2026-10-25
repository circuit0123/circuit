import { AudiencePage } from "@/components/AudiencePage";
import { page } from "@/content/pages";
import { pageMetadata } from "@/lib/metadata";

export const metadata = pageMetadata(page("partners"));

export default function Page() {
  return <AudiencePage slug="partners" />;
}
