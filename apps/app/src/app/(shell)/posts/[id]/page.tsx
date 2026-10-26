import { PostScreen } from "@/components/posts/PostScreen";

/** One build log, reached from a profile's grid, notifications and after posting. */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PostScreen id={Number(id)} />;
}
