import { LegalScreen } from "@/components/settings/LegalScreen";

/** Privacy policy, Terms and Community guidelines, from Settings → Help. An unknown name is a 404. */
export default async function Page({ params }: { params: Promise<{ doc: string }> }) {
  const { doc } = await params;
  return <LegalScreen doc={doc} />;
}
