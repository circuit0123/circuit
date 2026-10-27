"use client";

import { Button, ErrorState, GroupedList, ListRow, PushScreen, Skeleton } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { APP_VERSION } from "@/lib/env";
import { loadFailed, settingsHref, useMe, useSettings, useSignOut } from "@/data";
import { goBack } from "../jobs/JobScreen";
import { ROW_INSET } from "../sheets";
import { WorkEmailSheet } from "./WorkEmailSheet";

/** A settings sub-screen: pushed, with a Large title and Back to where it came from (Settings.dc.html, Appearance.dc.html). */
export function SettingsScreen({ title, backLabel = "Settings", back = settingsHref(), footer, children }: { title: string; backLabel?: string; back?: string; footer?: React.ReactNode; children: React.ReactNode }) {
  const router = useRouter();
  return (
    <PushScreen title={title} largeTitle backLabel={backLabel} onBack={() => goBack(router, back)} footer={footer} bleed>
      <div className="flex flex-col gap-7 pt-3">{children}</div>
    </PushScreen>
  );
}

/**
 * Settings (Settings.dc.html): Account, Appearance, Your data, Help, and Sign out, with the values each screen holds right on its row.
 * Everything comes from one call (GET /api/me/settings). Settings are core: never behind a flag.
 */
export function SettingsHome() {
  const router = useRouter();
  const s = useSettings();
  const me = useMe().data;
  const [verify, setVerify] = useState(false);
  const out = useSignOut();
  const v = s.summary;
  // Client-side moves (not <a href>), so the app and its cache stay put.
  const go = (href: string) => () => router.push(href);
  return (
    <SettingsScreen title="Settings" backLabel="Profile" back="/profile">
      {s.isError && !v && <ErrorState className="px-4 lg:px-0" text={loadFailed("your settings")} onRetry={() => void s.refetch()} />}
      {!v && !s.isError && <div className="flex flex-col gap-7 px-4 lg:px-0" aria-label="Loading settings"><Skeleton className="h-40" /><Skeleton className="h-14" /><Skeleton className="h-28" /></div>}
      {v && (
        <>
          <GroupedList header="Account">
            <ListRow className={ROW_INSET} title="Edit profile" subtitle={`${v.name} · ${v.emailHint}`} onClick={go(settingsHref("profile"))} />
            <ListRow className={ROW_INSET} title="Verification" value={me?.level && me.level >= 2 ? `Level ${me.level}` : "Level 1"} subtitle={me?.level && me.level >= 2 ? undefined : "Verify your work email"} onClick={me?.level && me.level >= 2 ? undefined : () => setVerify(true)} />
            <ListRow className={ROW_INSET} title="Privacy" value={v.privacy} onClick={go(settingsHref("privacy"))} />
            <ListRow className={ROW_INSET} title="Notifications" value={v.notifications} onClick={go(settingsHref("notifications"))} />
            <ListRow className={ROW_INSET} title="Blocked people" value={v.blocked ? String(v.blocked) : "None"} onClick={go(settingsHref("blocked"))} />
          </GroupedList>
          <GroupedList header="Appearance">
            <ListRow className={ROW_INSET} title="Appearance" value={v.appearance} onClick={go(settingsHref("appearance"))} />
          </GroupedList>
          <GroupedList header="Your data">
            <ListRow className={ROW_INSET} title="Export my data" onClick={go(settingsHref("export"))} />
            <ListRow className={ROW_INSET} title="Delete account" danger onClick={go(settingsHref("delete"))} />
          </GroupedList>
          <GroupedList header="Help">
            <ListRow className={ROW_INSET} title="Help and FAQ" onClick={go(settingsHref("help"))} />
            <ListRow className={ROW_INSET} title="Contact support" onClick={go(`${settingsHref("help")}#contact`)} />
            <ListRow className={ROW_INSET} title="Privacy policy" onClick={go(settingsHref("legal/privacy"))} />
            <ListRow className={ROW_INSET} title="Terms" onClick={go(settingsHref("legal/terms"))} />
            <ListRow className={ROW_INSET} title="Community guidelines" onClick={go(settingsHref("legal/guidelines"))} />
          </GroupedList>
          <div className="px-4 lg:px-0">
            <Button className="w-full" disabled={out.isPending} onClick={() => out.mutate(undefined, { onSuccess: () => router.replace("/") })}>Sign out</Button>
            <p className="t-footnote mt-6 px-4 text-text-muted">Circuit beta · Version {APP_VERSION} · Policy {v.policyVersion}</p>
          </div>
        </>
      )}
      <WorkEmailSheet open={verify} onClose={() => setVerify(false)} />
    </SettingsScreen>
  );
}
