"use client";

import { Settings } from "lucide-react";
import { Avatar, BarButton, Button, EmptyState, ErrorState, PrivateBadge, Screen, Section, Skeleton, VerifiedBadge, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { composeHref, loadFailed, memberHref, settingsHref, useMyProfile } from "@/data";
import { About, BuildLogGrid, CircuitsList, Highlights, OffersNeeds, ProfileTabs, StrengthMeter } from "./parts";

/**
 * Your own profile (Profile.dc.html, DESIGN.md §4 Profile): who you are, Edit profile and Share, the strength meter (only you see it),
 * what you offer and need with your highlights, then Build logs · Circuits · About. No follower, connection or view counts.
 */
export function Profile() {
  const router = useRouter();
  const toast = useToast();
  const q = useMyProfile();
  const p = q.data;
  const gear = <BarButton label="Settings" onClick={() => router.push(settingsHref())}><Settings size={22} strokeWidth={1.75} /></BarButton>;

  const share = async () => {
    const url = `${window.location.origin}${memberHref(p!.id)}`;
    try {
      if (navigator.share) { await navigator.share({ title: p!.name, url }); return; }
      await navigator.clipboard.writeText(url);
      toast({ text: "Link copied." });
    } catch { /* the share sheet was closed */ }
  };

  if (q.isError && !p) {
    return <Screen title="Profile" right={gear}><Section><ErrorState text={loadFailed("your profile")} onRetry={q.refetch} /></Section></Screen>;
  }
  if (!p) {
    return (
      <Screen title="Profile" right={gear}>
        <Section label="Loading your profile">
          <div className="flex items-center gap-4" aria-hidden><Skeleton round className="h-16 w-16" /><Skeleton className="h-4 w-40" /></div>
          <Skeleton className="mt-5 h-12" />
          <Skeleton className="mt-5 h-11" />
        </Section>
      </Screen>
    );
  }

  return (
    <Screen title={p.name} right={gear}>
      <Section label="About you">
        <div className="flex items-center gap-4">
          <Avatar id={p.id} name={p.name} size={64} />
          <div className="min-w-0">
            <p className="t-subhead flex flex-wrap items-center gap-1.5 text-text-muted">{p.line}<VerifiedBadge level={p.level} /></p>
            {p.org && <p className="t-subhead text-text-muted">{p.org}</p>}
            {p.minor && <PrivateBadge className="mt-1" />}
          </div>
        </div>
        {p.bio && <p className="t-body mt-5 max-w-[540px]">{p.bio}</p>}
        {p.minor && <p className="t-subhead mt-3 text-text-muted">Your profile is private. Only your connections and people in your organisation can see it.</p>}
        <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-3">
          <Button onClick={() => router.push(settingsHref("profile"))}>Edit profile</Button>
          <Button onClick={() => void share()}>Share</Button>
          {/* The gear lives in the phone's top bar; desktop has no top bar, so Settings is a button here. */}
          <div className="hidden lg:block"><Button className="w-full" onClick={() => router.push(settingsHref())}>Settings</Button></div>
        </div>
        {q.strength && <div className="mt-5"><StrengthMeter strength={q.strength} /></div>}
      </Section>

      <Section title="What I offer and need">
        <div className="flex flex-col gap-6">
          <OffersNeeds offers={p.offers} needs={p.needs} empty={<EmptyState text="Add what you can offer and what you need, so we can find your people." action={<Button onClick={() => router.push(settingsHref("profile"))}>Add them</Button>} />} />
          <Highlights items={p.highlights} />
        </div>
      </Section>

      <Section label="Your work">
        <ProfileTabs
          logs={q.posts.on}
          circuits={p.circuits !== null}
          render={(t) =>
            t === "logs" ? (
              <BuildLogGrid
                posts={q.posts.posts}
                isPending={q.posts.isPending}
                isError={q.posts.isError}
                onRetry={() => void q.posts.refetch()}
                empty={<EmptyState text="Your build logs show here. Share what you're working on." action={composeHref ? <Button onClick={() => router.push(composeHref!)}>New build log</Button> : undefined} />}
              />
            ) : t === "circuits" ? (
              <CircuitsList items={p.circuits ?? []} empty="Circuits you take part in show here." />
            ) : (
              <About p={p} />
            )
          }
        />
      </Section>
    </Screen>
  );
}
