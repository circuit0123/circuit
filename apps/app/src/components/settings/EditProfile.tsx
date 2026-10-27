"use client";

import { AddChip, Avatar, Button, Chip, Skeleton, TextArea, TextField, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { photoProblem, useCapabilities, useMe, useProfileDraft, useProfilePhoto, useSaveProfile, type ProfileEdit } from "@/data";
import { goBack } from "../jobs/JobScreen";
import { CapabilitySheet, ConfirmSheet } from "../sheets";
import { SettingsScreen } from "./SettingsHome";

const LIMITS = { offers: 5, needs: 3, skills: 8 } as const;
type ListKey = keyof typeof LIMITS;

/** The profile photo saves on its own as soon as it is chosen; it is not part of Save. */
function PhotoRow() {
  const me = useMe().data;
  const photo = useProfilePhoto();
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const choose = (f: File | undefined) => {
    if (!f) return;
    const why = photoProblem(f);
    if (why) return toast({ text: why, tone: "error" });
    photo.set.mutate(f, { onSuccess: () => toast({ text: "Photo updated." }), onError: () => toast({ text: "Couldn't upload that photo. Try again.", tone: "error" }) });
  };
  const busy = photo.set.isPending || photo.remove.isPending;
  return (
    <div className="flex items-center gap-4">
      <Avatar id={me?.id ?? 0} name={me?.name || "You"} src={me?.photo ?? null} size={64} />
      <div className="flex flex-col items-start">
        <Button variant="text" className="-ml-5" disabled={busy} onClick={() => input.current?.click()}>{photo.set.isPending ? "Uploading…" : me?.photo ? "Change photo" : "Add a photo"}</Button>
        {me?.photo && <Button variant="text" className="-ml-5" disabled={busy} onClick={() => photo.remove.mutate(undefined, { onSuccess: () => toast({ text: "Photo removed." }) })}>Remove photo</Button>}
      </div>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Photo file" hidden onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
    </div>
  );
}

/**
 * Edit profile: name, a few lines about you, city and college, what you offer and need (from the fixed list), and skills with a
 * proof-of-work link. The strength meter's steps link straight to each part (#bio, #offers, #needs, #skills).
 */
export function EditProfile() {
  const router = useRouter();
  const toast = useToast();
  const start = useProfileDraft();
  const save = useSaveProfile();
  const caps = useCapabilities();
  const names = new Map((caps.data ?? []).map((c) => [c.slug, c.name]));
  const [draft, setDraft] = useState<ProfileEdit | null>(null);
  const [picking, setPicking] = useState<ListKey | null>(null);
  const [leaving, setLeaving] = useState(false);
  useEffect(() => { if (start && !draft) setDraft(start); }, [start, draft]); // eslint-disable-line react-hooks/set-state-in-effect
  // Deep links from the strength meter land on their part once it's drawn.
  useEffect(() => {
    if (draft && window.location.hash) document.getElementById(window.location.hash.slice(1))?.scrollIntoView({ block: "center" });
  }, [!!draft]); // eslint-disable-line react-hooks/exhaustive-deps

  const dirty = !!draft && !!start && JSON.stringify(draft) !== JSON.stringify(start);
  const set = (p: Partial<ProfileEdit>) => setDraft((d) => (d ? { ...d, ...p } : d));
  const slugs = (k: ListKey) => (k === "skills" ? draft!.skills.map((s) => s.slug) : draft![k]);
  const toggle = (k: ListKey, slug: string) => {
    if (!draft) return;
    if (k === "skills") set({ skills: draft.skills.some((s) => s.slug === slug) ? draft.skills.filter((s) => s.slug !== slug) : [...draft.skills, { slug, proof: "" }] });
    else set({ [k]: draft[k].includes(slug) ? draft[k].filter((s) => s !== slug) : [...draft[k], slug] });
  };
  const nameError = draft && !draft.name.trim() ? "Your name can't be empty." : null;
  const badProof = draft?.skills.find((s) => s.proof.trim() && !/^https?:\/\/\S+\.\S+/.test(s.proof.trim()));

  const submit = () => {
    if (!draft || nameError || badProof) return;
    save.mutate(draft, {
      onSuccess: () => { toast({ text: "Profile saved." }); router.push("/profile"); },
      onError: () => toast({ text: "Couldn't save. Check your connection and try again.", tone: "error" }),
    });
  };

  const chips = (k: ListKey, title: string, hint: string) => (
    <section id={k} aria-labelledby={`${k}-h`} className="scroll-mt-16 px-4 lg:px-0">
      <h2 id={`${k}-h`} className="t-headline">{title}</h2>
      <p className="t-subhead mb-3 mt-1 text-text-muted">{hint}</p>
      <div className="flex flex-wrap gap-2" role="group" aria-label={title}>
        {slugs(k).map((s) => <Chip key={s} label={names.get(s) ?? s} onRemove={() => toggle(k, s)} />)}
        {slugs(k).length < LIMITS[k] && <AddChip label={`Add to ${title.toLowerCase()}`} onClick={() => setPicking(k)} className="!min-h-8 !px-3 t-subhead" />}
      </div>
    </section>
  );

  return (
    <SettingsScreen
      title="Edit profile"
      backLabel="Profile"
      back="/profile"
      footer={draft && <Button variant="primary" className="w-full" disabled={!dirty || !!nameError || !!badProof || save.isPending} onClick={submit}>{save.isPending ? "Saving…" : "Save"}</Button>}
    >
      {!draft ? (
        <div className="flex flex-col gap-5 px-4 lg:px-0" aria-label="Loading your profile"><Skeleton className="h-12" /><Skeleton className="h-36" /><Skeleton className="h-12" /></div>
      ) : (
        <>
          <div className="flex flex-col gap-5 px-4 lg:px-0">
            <PhotoRow />
            <TextField label="Name" value={draft.name} onChange={(e) => set({ name: e.target.value })} maxLength={120} autoComplete="name" error={nameError} />
            <div id="bio" className="scroll-mt-16">
              <TextArea label="About you" value={draft.bio} onChange={(e) => set({ bio: e.target.value })} maxLength={2000} hint="Two lines on what you're building or learning." className="[&_textarea]:h-32" />
            </div>
            <TextField label="City" value={draft.city} onChange={(e) => set({ city: e.target.value })} maxLength={100} autoComplete="address-level2" />
            <TextField label="College or organisation" value={draft.college} onChange={(e) => set({ college: e.target.value })} maxLength={200} />
          </div>
          {chips("offers", "What I offer", `Up to ${LIMITS.offers}. What you can help others with.`)}
          {chips("needs", "What I need", `Up to ${LIMITS.needs}. What you'd like help with now.`)}
          {chips("skills", "Skills", "Add a link to something you made: a repo, a demo, a design.")}
          {draft.skills.length > 0 && (
            <div className="flex flex-col gap-4 px-4 lg:px-0">
              {draft.skills.map((s) => (
                <TextField
                  key={s.slug}
                  label={`Proof of work for ${names.get(s.slug) ?? s.slug}`}
                  type="url"
                  inputMode="url"
                  placeholder="https://"
                  value={s.proof}
                  maxLength={200}
                  onChange={(e) => set({ skills: draft.skills.map((x) => (x.slug === s.slug ? { ...x, proof: e.target.value } : x)) })}
                  error={badProof?.slug === s.slug ? "Start the link with https://" : null}
                />
              ))}
            </div>
          )}
          {dirty && (
            <div className="px-4 lg:px-0">
              <Button variant="text" className="w-full" onClick={() => setLeaving(true)}>Discard changes</Button>
            </div>
          )}
        </>
      )}
      {picking && draft && (
        <CapabilitySheet
          open
          onClose={() => setPicking(null)}
          title={picking === "offers" ? "What I offer" : picking === "needs" ? "What I need" : "Skills"}
          chosen={slugs(picking)}
          limit={LIMITS[picking]}
          onToggle={(slug) => toggle(picking, slug)}
        />
      )}
      <ConfirmSheet
        open={leaving}
        onClose={() => setLeaving(false)}
        title="Discard your changes?"
        text="What you changed here won't be saved."
        confirmLabel="Discard"
        onConfirm={() => { setLeaving(false); goBack(router, "/profile"); }}
      />
    </SettingsScreen>
  );
}
