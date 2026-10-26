import { Person } from "@/components/profile/Person";

/** Someone's profile, reached from Pulse, matches, Discover → People, founders on a Startup page and replies. */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Person id={Number(id)} />;
}
