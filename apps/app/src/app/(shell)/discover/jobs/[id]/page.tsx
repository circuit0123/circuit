import { JobScreen } from "@/components/jobs/JobScreen";

/** A role's page, pushed over Discover (the shell draws it without the tab bar). */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <JobScreen id={Number(id)} />;
}
