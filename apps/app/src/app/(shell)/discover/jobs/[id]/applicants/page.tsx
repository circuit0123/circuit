import { Applicants } from "@/components/jobs/Applicants";

/** A role's applicants, ranked by skill match. Founders of that startup only; anyone else gets the 404 screen. */
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <Applicants jobId={Number(id)} />;
}
