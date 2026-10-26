"use client";

import { AddChip, AddMedia, Button, CharCounter, Chip, CropFrame, GroupedList, ListRow, MediaSlot, SegmentedControl, Sheet, TextField, cx, useToast } from "@circuit/ui";
import { notFound, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { BODY_MAX, MAX_PHOTOS, MAX_TAGS, VISIBILITY, photoProblemText, postHref, useCapabilities, useComposer, useFeatures, type Aspect, type Visibility } from "@/data";
import { goBack } from "../jobs/JobScreen";
import { CapabilitySheet, ConfirmSheet, ROW_INSET } from "../sheets";

/**
 * New build log (Composer.dc.html, DESIGN.md §4 Build log): media first (up to 4, crop only, shrunk on the phone), then what you built
 * with a 500-character counter, up to 3 capability chips, an optional link and who can see it. Under-18 members post to their
 * organisation by default. Each photo uploads as soon as it's added, with its own progress and Retry. Hidden with `pulse` off.
 */
export function Composer() {
  const router = useRouter();
  const toast = useToast();
  const features = useFeatures();
  const c = useComposer();
  const caps = useCapabilities();
  const names = new Map((caps.data ?? []).map((x) => [x.slug, x.name]));
  const file = useRef<HTMLInputElement>(null);
  const [sheet, setSheet] = useState<null | "tags" | "visibility" | "link" | "discard">(null);
  const [photo, setPhoto] = useState<string | null>(null);
  const [linkDraft, setLinkDraft] = useState("");
  const [focus, setFocus] = useState<{ x: number; y: number } | null>(null);
  if (features.ready && !features.on("pulse")) notFound();

  const open = photo ? c.photos.find((p) => p.key === photo) : undefined;
  const cancel = () => (c.dirty ? setSheet("discard") : goBack(router, "/"));
  const post = () => c.publish.mutate(undefined, {
    onSuccess: (p) => { toast({ text: "Posted." }); router.replace(postHref(p.id)); },
  });
  let host = "";
  try { host = c.link ? new URL(c.link).hostname.replace(/^www\./, "") : ""; } catch { host = c.link; }

  return (
    <div className="min-h-dvh bg-bg">
      <header className="material sticky top-0 z-20 grid min-h-11 grid-cols-[1fr_auto_1fr] items-center border-b border-separator px-4 pt-[env(safe-area-inset-top)]">
        <button type="button" onClick={cancel} className="min-h-11 justify-self-start t-body text-text-muted active:opacity-80">Cancel</button>
        <h1 className="t-headline whitespace-nowrap">New build log</h1>
        <button
          type="button"
          onClick={post}
          disabled={!!c.blocker || c.publish.isPending}
          className="min-h-8 justify-self-end rounded-full bg-primary px-4 t-subhead font-semibold text-on-primary transition-transform active:scale-[0.97] disabled:opacity-50"
        >
          {c.publish.isPending ? "Posting…" : "Post"}
        </button>
      </header>

      <div className="mx-auto w-full max-w-[600px] px-4 pb-24 pt-5">
        <input
          ref={file}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif"
          multiple
          className="sr-only"
          tabIndex={-1}
          aria-hidden
          data-testid="photo-input"
          onChange={async (e) => {
            const files = Array.from(e.target.files ?? []);
            e.target.value = "";
            const problem = await c.addFiles(files);
            if (problem) toast({ text: photoProblemText[problem], tone: "error" });
          }}
        />
        {c.photos.length === 0 ? (
          <AddMedia onClick={() => file.current?.click()} />
        ) : (
          <section aria-label="Photos">
            <div className="grid grid-cols-2 gap-2">
              {c.photos.map((p, i) => (
                <MediaSlot
                  key={p.key}
                  src={p.preview}
                  label={`Photo ${i + 1} of ${c.photos.length}`}
                  state={p.state}
                  progress={p.progress}
                  needsAlt={!p.alt.trim()}
                  aspect={c.aspect}
                  focus={p.focus}
                  onOpen={() => { setPhoto(p.key); setFocus(p.focus); }}
                  onRemove={() => c.remove(p.key)}
                  onRetry={() => void c.retry(p.key)}
                />
              ))}
              {c.photos.length < MAX_PHOTOS && <AddMedia compact aspect={c.aspect} label="Add photo" onClick={() => file.current?.click()} />}
            </div>
            <div className="mt-3 flex items-center justify-between gap-4">
              <span className="t-subhead text-text-muted">Frame</span>
              <SegmentedControl<Aspect> label="Photo frame" items={[{ id: "4:5", label: "Portrait" }, { id: "1:1", label: "Square" }]} value={c.aspect} onChange={c.setAspect} />
            </div>
          </section>
        )}

        <label className="mt-5 block">
          <span className="sr-only">What did you build?</span>
          <textarea
            value={c.body}
            onChange={(e) => c.setBody(e.target.value)}
            maxLength={BODY_MAX}
            rows={4}
            placeholder="What did you build or learn?"
            className="t-body block w-full resize-none bg-transparent text-text outline-none placeholder:text-text-subtle"
          />
        </label>
        <CharCounter count={c.body.length} max={BODY_MAX} />

        <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label="Capabilities">
          {c.tags.map((t) => <Chip key={t} label={names.get(t) ?? t} onRemove={() => c.toggleTag(t)} />)}
          {c.tags.length < MAX_TAGS && <AddChip label="Add a skill" onClick={() => setSheet("tags")} className="!min-h-8 !px-3 t-subhead" />}
        </div>

        <GroupedList className="mt-7 !px-0">
          <ListRow className={ROW_INSET} title="Who can see this" value={VISIBILITY.find((v) => v.id === c.visibility)?.label} onClick={() => setSheet("visibility")} />
          <ListRow className={ROW_INSET} title={c.link ? "Link" : "Add a link"} value={host || "GitHub, demo, Figma"} onClick={() => { setLinkDraft(c.link); setSheet("link"); }} />
        </GroupedList>

        {c.dirty && c.blocker && <p className="t-footnote mt-4 text-text-muted" role="status">{c.blocker}</p>}
        {c.publishProblem && <p className="t-footnote mt-4 text-danger" role="alert">{c.publishProblem}</p>}
      </div>

      <CapabilitySheet open={sheet === "tags"} onClose={() => setSheet(null)} title="Tag up to 3 skills" chosen={c.tags} limit={MAX_TAGS} onToggle={c.toggleTag} />

      <Sheet open={sheet === "visibility"} onClose={() => setSheet(null)} title="Who can see this" detents={["medium"]}>
        <div role="radiogroup" aria-label="Who can see this" className="flex flex-col">
          {VISIBILITY.map((v) => {
            const locked = v.id === "everyone" && c.minor;
            return (
              <button
                key={v.id}
                type="button"
                role="radio"
                aria-checked={c.visibility === v.id}
                disabled={locked}
                onClick={() => { c.setVisibility(v.id as Visibility); setSheet(null); }}
                className="flex min-h-14 items-center justify-between border-b border-separator text-left t-body disabled:opacity-50"
              >
                {v.label}
                <span aria-hidden className={cx("h-5 w-5 rounded-full border-2", c.visibility === v.id ? "border-text bg-text" : "border-text-subtle")} />
              </button>
            );
          })}
        </div>
        {c.minor && <p className="t-footnote mt-3 text-text-muted">Posting to everyone opens once your age is verified.</p>}
      </Sheet>

      <Sheet open={sheet === "link"} onClose={() => setSheet(null)} title="Add a link" detents={["medium"]}>
        <TextField
          label="Link"
          type="url"
          inputMode="url"
          placeholder="https://github.com/you/project"
          value={linkDraft}
          onChange={(e) => setLinkDraft(e.target.value)}
          hint="GitHub, a live demo or a Figma file."
        />
        <Button variant="primary" className="mt-6 w-full" onClick={() => { c.setLink(linkDraft.trim()); setSheet(null); }}>Done</Button>
        {c.link && <Button variant="text" className="mt-2 w-full" onClick={() => { c.setLink(""); setSheet(null); }}>Remove link</Button>}
      </Sheet>

      <Sheet open={!!open} onClose={() => setPhoto(null)} title="Crop and describe" detent="large" detents={["large"]}>
        {open && (
          <>
            <CropFrame src={open.preview} aspect={c.aspect} focus={focus ?? open.focus} onChange={setFocus} />
            <TextField
              className="mt-5"
              label="Description"
              value={open.alt}
              onChange={(e) => c.setAlt(open.key, e.target.value)}
              placeholder="What the photo shows"
              hint="Read out to people using a screen reader. Required."
              maxLength={300}
            />
            <Button
              variant="primary"
              className="mt-6 w-full"
              onClick={() => {
                if (focus && (focus.x !== open.focus.x || focus.y !== open.focus.y)) c.setFocus(open.key, focus);
                setPhoto(null);
              }}
            >
              Done
            </Button>
            <Button variant="destructive" className="mt-3 w-full" onClick={() => { c.remove(open.key); setPhoto(null); }}>Remove photo</Button>
          </>
        )}
      </Sheet>

      <ConfirmSheet
        open={sheet === "discard"}
        onClose={() => setSheet(null)}
        title="Discard this build log?"
        text="What you wrote and the photos you added will be lost."
        confirmLabel="Discard"
        onConfirm={() => { setSheet(null); goBack(router, "/"); }}
      />
    </div>
  );
}
