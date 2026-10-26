import { StartupScreen } from "@/components/startups/StartupScreen";

/** A startup's page, reached from the map sheet, Discover → Startups, job pages and Pulse. */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <StartupScreen id={Number(id)} />;
}
