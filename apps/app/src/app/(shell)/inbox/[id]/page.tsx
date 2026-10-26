import { ConversationScreen } from "@/components/inbox/Conversation";

/** One conversation, pushed from the Inbox, a notification or a Live wire Reply. */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ConversationScreen id={Number(id)} />;
}
