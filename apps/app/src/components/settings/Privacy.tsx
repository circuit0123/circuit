"use client";

import { ErrorState, GroupedList, ListRow, Skeleton, Toggle, cx, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { VISIBILITY_OPTIONS, loadFailed, settingsHref, usePrivacy, useSettings } from "@/data";
import { ROW_INSET } from "../sheets";
import { SettingsScreen } from "./SettingsHome";

/**
 * Privacy: who can see your profile, whether your organisation can, whether you show up in circuits, and whether people you aren't
 * connected to can send you a request. Under 18, a public profile and requests from strangers are locked, and the screen says why.
 */
export function Privacy() {
  const router = useRouter();
  const toast = useToast();
  const s = useSettings();
  const { save, problem } = usePrivacy();
  useEffect(() => { if (problem) toast({ text: problem, tone: "error" }); }, [problem, toast]);
  const p = s.data?.privacy;
  const minor = s.data?.profile.is_minor ?? false;
  const level = s.data?.profile.verification_level ?? 0;
  return (
    <SettingsScreen title="Privacy">
      {s.isError && !p && <ErrorState className="px-4 lg:px-0" text={loadFailed("your privacy settings")} onRetry={() => void s.refetch()} />}
      {!p && !s.isError && <div className="flex flex-col gap-7 px-4 lg:px-0" aria-label="Loading privacy"><Skeleton className="h-44" /><Skeleton className="h-40" /></div>}
      {p && (
        <>
          <GroupedList header="Who can see your profile" footer={minor ? "Because you're under 18, your profile can't be public. People in your organisation and your connections can always see it." : VISIBILITY_OPTIONS.find((v) => v.id === p.profile_visibility)?.hint}>
            {VISIBILITY_OPTIONS.map((v) => {
              const locked = minor && v.id === "public";
              const on = p.profile_visibility === v.id;
              return (
                <button
                  key={v.id}
                  type="button"
                  role="radio"
                  aria-checked={on}
                  disabled={locked}
                  onClick={() => save.mutate({ profile_visibility: v.id })}
                  className={`flex min-h-row w-full items-center justify-between px-4 text-left t-body disabled:opacity-50 ${ROW_INSET}`}
                >
                  {v.label}{locked && <span className="sr-only"> (not available under 18)</span>}
                  <span aria-hidden className={cx("h-5 w-5 rounded-full border-2", on ? "border-text bg-text" : "border-text-subtle")} />
                </button>
              );
            })}
          </GroupedList>
          <GroupedList footer={[
            level < 2 && !p.circuits_opt_in ? "Circuits need a verified work email (level 2)." : null,
            minor ? "Under 18, only your connections can message you." : null,
          ].filter(Boolean).join(" ") || undefined}>
            <ListRow className={ROW_INSET} title="Visible to my organisation" subtitle="Your partner organisation can see your profile, not just counts" trailing={<Toggle label="Visible to my organisation" checked={p.visible_to_org} onChange={(on) => save.mutate({ visible_to_org: on })} />} />
            <ListRow className={ROW_INSET} title="Show me in circuits" subtitle="Weekly three-person exchanges" trailing={<Toggle label="Show me in circuits" checked={p.circuits_opt_in} disabled={level < 2 && !p.circuits_opt_in} onChange={(on) => save.mutate({ circuits_opt_in: on })} />} />
            <ListRow className={ROW_INSET} title="Message requests" subtitle="From people you aren't connected to" trailing={<Toggle label="Message requests from people you aren't connected to" checked={p.allow_requests} disabled={minor} onChange={(on) => save.mutate({ allow_requests: on })} />} />
          </GroupedList>
          <GroupedList>
            <ListRow className={ROW_INSET} title="Blocked people" value={s.data!.blocked_count ? String(s.data!.blocked_count) : "None"} onClick={() => router.push(settingsHref("blocked"))} />
          </GroupedList>
        </>
      )}
    </SettingsScreen>
  );
}
