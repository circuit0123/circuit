import { DraftConversationScreen } from "@/components/inbox/Conversation";

/** A first message to someone: `/inbox/new?to=<member id>`. Opens the existing conversation instead when there is one. */
export default async function Page({ searchParams }: { searchParams: Promise<{ to?: string }> }) {
  const { to } = await searchParams;
  return <DraftConversationScreen memberId={Number(to)} />;
}
