import { ExportData } from "@/components/settings/ExportData";

/** Export my data; with `?token=` (the link in the export email) it offers the download. */
export default async function Page({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams;
  return <ExportData token={token ?? null} />;
}
