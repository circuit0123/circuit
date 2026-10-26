"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { ago, skillFit } from "@/lib/format";
import { api, ApiError, unwrap } from "./client";
import { toJobRow, visibleTo, type JobRow } from "./discover";
import { useKey } from "./keys";
import { useMe } from "./me";
import type { MissingJobFields } from "./missing";

export type JobPage = JobRow & {
  location: string;
  description: string;
  skills: Array<{ name: string; have: boolean; required: boolean }>;
  matched: number;
  isOpen: boolean;
};

/** A job page (Job.dc.html): everything it draws in one call. Under-18 members get "not found" for a role from an unverified startup. */
export function useJob(id: number) {
  const me = useMe().data;
  const { key, enabled } = useKey("job", id);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && Number.isFinite(id),
    queryFn: async (): Promise<JobPage> => {
      const j = (await unwrap(api.GET("/api/jobs/{job_id}", { params: { path: { job_id: id } } }))) as Schemas["JobOut"] & MissingJobFields;
      // Required skills first, then the nice-to-haves; within each, the ones you have first.
      const skills = [...j.capabilities]
        .sort((a, b) => Number(b.required) - Number(a.required) || Number(b.your_level != null) - Number(a.your_level != null))
        .map((c) => ({ name: c.name, have: c.your_level != null, required: c.required }));
      return { ...toJobRow(j), location: j.location, description: j.description, skills, matched: skills.filter((s) => s.have).length, isOpen: j.is_open };
    },
  });
  const hidden = !!q.data && !visibleTo(me)(q.data);
  return { ...q, data: hidden ? undefined : q.data, notFound: hidden || (q.error instanceof ApiError && q.error.status === 404) };
}

/** One-click apply with your profile. The job page and the lists show "Applied" straight away. */
export function useApply() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: number) => unwrap(api.POST("/api/jobs/{job_id}/apply", { params: { path: { job_id: jobId } } })),
    onSuccess: (_a, jobId) => {
      qc.setQueryData<JobPage>(["job", jobId], (old) => old && { ...old, applied: true });
      void qc.invalidateQueries({ predicate: (x) => ["job", "applications", "discover-jobs", "startup-jobs"].includes(String(x.queryKey[0])) });
    },
  });
}

/** The founder reads a fresh application as "New"; the student who sent it reads "Sent". */
const FOUNDER_STATUS: Record<string, string> = { submitted: "New" };
const STATUS: Record<string, string> = { submitted: "Sent", shortlisted: "Shortlisted", rejected: "Not selected", hired: "Hired", withdrawn: "Withdrawn" };
export const applicationStatus = (s: string) => STATUS[s] ?? s;

export type ApplicationRow = { id: number; jobId: number; title: string; startup: string; startupId: number; status: string; statusKey: string; when: string };

/** "My applications": newest first, with a status in plain words. */
export function useMyApplications() {
  const { key, enabled } = useKey("applications");
  return useQuery({
    queryKey: key,
    enabled,
    queryFn: async (): Promise<ApplicationRow[]> =>
      (await unwrap(api.GET("/api/me/applications", { params: { query: { limit: 50 } } }))).items.map((a) => ({
        id: a.id, jobId: a.job_id, title: a.job_title, startup: a.startup_name, startupId: a.startup_id, status: applicationStatus(a.status), statusKey: a.status, when: ago(a.created_at),
      })),
  });
}

export type ApplicantRow = {
  applicationId: number;
  studentId: number;
  name: string;
  fit: string;
  skills: Array<{ name: string; level: number; proof: string }>;
  status: string;
  statusKey: string;
  when: string;
};

/**
 * The founder's applicant view: ranked by skill match, best first (CLAUDE.md F11), never by college. Founders of the startup only; the API
 * answers 403 to anyone else, which the screen shows as "not found".
 */
export function useApplicants(jobId: number) {
  const { key, enabled } = useKey("applicants", jobId);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && Number.isFinite(jobId),
    retry: false,
    queryFn: async (): Promise<ApplicantRow[]> => {
      const page = await unwrap(api.GET("/api/jobs/{job_id}/applicants", { params: { path: { job_id: jobId }, query: { limit: 100 } } }));
      return [...page.items].sort((a, b) => b.skill_match - a.skill_match).map((a) => ({
        applicationId: a.application_id,
        studentId: a.student_id,
        name: a.display_name,
        fit: skillFit(a.skill_match) ?? "Some of the skills",
        skills: a.skills.map((s) => ({ name: s.capability, level: s.level, proof: s.proof_url })),
        status: FOUNDER_STATUS[a.status] ?? applicationStatus(a.status),
        statusKey: a.status,
        when: ago(a.applied_at),
      }));
    },
  });
  const denied = q.error instanceof ApiError && (q.error.status === 403 || q.error.status === 404);
  return { ...q, denied };
}

/** Shortlist, turn down or mark hired. Optimistic: the row changes at once and comes back if the call fails. */
export function useSetApplicantStatus(jobId: number) {
  const qc = useQueryClient();
  const { key } = useKey("applicants", jobId);
  return useMutation({
    mutationFn: ({ applicationId, status }: { applicationId: number; status: "shortlisted" | "rejected" | "hired" }) =>
      unwrap(api.PATCH("/api/applications/{application_id}", { params: { path: { application_id: applicationId } }, body: { status } })),
    onMutate: ({ applicationId, status }) => {
      qc.setQueryData<ApplicantRow[]>(key, (old) => old?.map((a) => (a.applicationId === applicationId ? { ...a, statusKey: status, status: applicationStatus(status) } : a)));
    },
    onError: () => qc.invalidateQueries({ queryKey: key }),
  });
}

/** Stipend and type for a role row on the Startup page, plus its fit in words. */
export function useStartupJobs(startupId: number | null) {
  const me = useMe().data;
  const { key, enabled } = useKey("startup-jobs", startupId);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && startupId !== null,
    queryFn: async () => ((await unwrap(api.GET("/api/jobs", { params: { query: { startup_id: startupId!, limit: 20 } } }))).items as Array<Schemas["JobOut"] & MissingJobFields>).map(toJobRow),
  });
  return { ...q, data: q.data?.filter(visibleTo(me)) };
}
