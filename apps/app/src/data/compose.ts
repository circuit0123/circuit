"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { aspectFor, cropAndResize, imageSize, type Aspect } from "@/lib/image";
import { putWithProgress } from "@/lib/upload";
import { api, ApiError, unwrap } from "./client";
import { MAX_IMAGE_BYTES } from "./conversation";
import { useMe } from "./me";

export type { Aspect };
export type Visibility = "everyone" | "connections" | "organisation";
export const VISIBILITY: Array<{ id: Visibility; label: string }> = [
  { id: "everyone", label: "Everyone" },
  { id: "connections", label: "Connections" },
  { id: "organisation", label: "My organisation" },
];

/** Limits from DESIGN.md §4 Build log (and PostIn). */
export const BODY_MAX = 500;
export const MAX_PHOTOS = 4;
export const MAX_TAGS = 3;
/** A photo straight off a phone can be big; it is shrunk before upload, so only absurd files are refused up front. */
const MAX_ORIGINAL_BYTES = 30 * 1024 * 1024;

export type DraftPhoto = {
  key: string;
  /** The original, kept so a new crop starts from full quality. */
  file: File;
  preview: string;
  width: number;
  height: number;
  focus: { x: number; y: number };
  alt: string;
  state: "processing" | "uploading" | "done" | "failed";
  progress: number;
  uploadId: number | null;
};

export type PhotoProblem = "count" | "type" | "too_big" | "unreadable";
export const photoProblemText: Record<PhotoProblem, string> = {
  count: "A build log takes up to 4 photos.",
  type: "Choose a photo: JPEG, PNG, WebP or HEIC.",
  too_big: "That photo is too big. Choose one under 30 MB.",
  unreadable: "Couldn't read that photo. Try a JPEG or PNG.",
};

const validLink = (s: string) => {
  if (!s.trim()) return true;
  try { const u = new URL(s.trim()); return u.protocol === "https:" || u.protocol === "http:"; } catch { return false; }
};

/**
 * The build log composer (Composer.dc.html). Owns the draft and the uploads:
 * - photos: up to 4, each cropped to the shared frame (4:5 or 1:1, set by the first photo) and shrunk on the phone, then uploaded at
 *   once (sign → PUT with progress → complete). A failed upload says so on its tile and `retry` sends it again. A new crop re-uploads.
 * - text up to 500 characters, up to 3 capability tags, an optional link, and who can see it. Under-18 members start on "My
 *   organisation" and can't pick Everyone until their age is verified (DESIGN.md §4).
 * - `blocker`: why Post is disabled right now, in one sentence (null when it can post).
 */
export function useComposer() {
  const me = useMe().data;
  const minor = me?.isMinor ?? false;
  const qc = useQueryClient();
  const [photos, setPhotos] = useState<DraftPhoto[]>([]);
  const [aspect, setAspectState] = useState<Aspect>("4:5");
  const [body, setBody] = useState("");
  const [tags, setTags] = useState<string[]>([]);
  const [link, setLink] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("everyone");
  const [picked, setPicked] = useState(false);
  // Under-18: My organisation by default (settled once the member is known, unless they already chose).
  useEffect(() => { if (minor && !picked) setVisibility("organisation"); }, [minor, picked]); // eslint-disable-line react-hooks/set-state-in-effect

  // The photos and frame live in refs too, so the async upload steps always read the newest; `apply` keeps the two in step.
  const latest = useRef<DraftPhoto[]>([]);
  const aspectRef = useRef<Aspect>("4:5");
  const apply = useCallback((next: (list: DraftPhoto[]) => DraftPhoto[]) => { latest.current = next(latest.current); setPhotos(latest.current); }, []);
  const attempt = useRef(new Map<string, number>());
  const seq = useRef(0);

  const patch = useCallback((key: string, p: Partial<DraftPhoto>) => apply((list) => list.map((x) => (x.key === key ? { ...x, ...p } : x))), [apply]);

  const upload = useCallback(async (key: string) => {
    const n = (attempt.current.get(key) ?? 0) + 1;
    attempt.current.set(key, n);
    const current = () => attempt.current.get(key) === n;
    const ph = latest.current.find((x) => x.key === key);
    if (!ph) return;
    patch(key, { state: "processing", progress: 0, uploadId: null });
    try {
      const out = await cropAndResize(ph.file, aspectRef.current, ph.focus);
      if (out.blob.size > MAX_IMAGE_BYTES) throw new Error("too big after resize");
      if (!current()) return;
      patch(key, { state: "uploading" });
      const up = await unwrap(api.POST("/api/media/uploads", { body: { purpose: "post", content_type: "image/jpeg", size: out.blob.size } }));
      await putWithProgress(up.upload_url, out.blob, (f) => { if (current()) patch(key, { progress: Math.min(0.95, f) }); });
      await unwrap(api.POST("/api/media/uploads/{upload_id}/complete", { params: { path: { upload_id: up.id } } }));
      if (current()) patch(key, { state: "done", progress: 1, uploadId: up.id });
    } catch {
      if (current()) patch(key, { state: "failed", progress: 0 });
    }
  }, [patch]);

  /** Adds photos from a file picker. Returns the first problem, if any, so the screen can say it once. */
  const addFiles = useCallback(async (files: File[]): Promise<PhotoProblem | null> => {
    let problem: PhotoProblem | null = null;
    const room = MAX_PHOTOS - latest.current.length;
    if (files.length > room) problem = "count";
    const added: DraftPhoto[] = [];
    for (const file of files.slice(0, Math.max(0, room))) {
      if (!file.type.startsWith("image/") && !/\.hei[cf]$/i.test(file.name)) { problem ??= "type"; continue; }
      if (file.size > MAX_ORIGINAL_BYTES) { problem ??= "too_big"; continue; }
      let size;
      try { size = await imageSize(file); } catch { problem ??= "unreadable"; continue; }
      added.push({ key: `p${++seq.current}`, file, preview: URL.createObjectURL(file), ...size, focus: { x: 0.5, y: 0.5 }, alt: "", state: "processing", progress: 0, uploadId: null });
    }
    if (added.length) {
      if (latest.current.length === 0) { const a = aspectFor(added[0].width, added[0].height); aspectRef.current = a; setAspectState(a); }
      apply((list) => [...list, ...added]);
      for (const p of added) void upload(p.key);
    }
    return problem;
  }, [upload, apply]);

  const remove = useCallback((key: string) => {
    attempt.current.set(key, -1);
    const p = latest.current.find((x) => x.key === key);
    if (p) URL.revokeObjectURL(p.preview);
    apply((list) => list.filter((x) => x.key !== key));
  }, [apply]);

  /** A new crop for one photo: saved, then uploaded again. */
  const setFocus = useCallback((key: string, focus: { x: number; y: number }) => {
    apply((list) => list.map((x) => (x.key === key ? { ...x, focus } : x)));
    void upload(key);
  }, [upload, apply]);

  /** The frame for every photo (the pager keeps one shape). Changing it re-crops and re-uploads them all. */
  const setAspect = useCallback((a: Aspect) => {
    if (a === aspectRef.current) return;
    aspectRef.current = a;
    setAspectState(a);
    for (const p of latest.current) void upload(p.key);
  }, [upload]);

  useEffect(() => {
    const list = latest;
    return () => { for (const p of list.current) URL.revokeObjectURL(p.preview); };
  }, []);

  const publish = useMutation({
    mutationFn: () => unwrap(api.POST("/api/posts", {
      body: {
        visibility,
        body: body.trim(),
        capabilities: tags,
        link: link.trim(),
        media: photos.map((p) => ({ upload_id: p.uploadId!, alt_text: p.alt.trim() })),
      },
    })),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["pulse"] }); qc.invalidateQueries({ queryKey: ["member-posts"] }); },
  });

  const blocker =
    !body.trim() && photos.length === 0 ? "Add a photo or write what you built."
      : body.length > BODY_MAX ? `Keep it under ${BODY_MAX} characters.`
      : photos.some((p) => p.state === "failed") ? "One photo didn't upload. Retry it or remove it."
      : photos.some((p) => p.state !== "done") ? "Your photos are still uploading."
      : photos.some((p) => !p.alt.trim()) ? "Add a description to each photo, for people using a screen reader."
      : !validLink(link) ? "That link doesn't look right. Start it with https://"
      : null;

  return {
    minor,
    photos, aspect, setAspect, addFiles, remove, retry: upload, setFocus,
    setAlt: (key: string, alt: string) => patch(key, { alt: alt.slice(0, 300) }),
    body, setBody: (s: string) => setBody(s.slice(0, BODY_MAX)),
    tags, toggleTag: (slug: string) => setTags((t) => (t.includes(slug) ? t.filter((x) => x !== slug) : t.length < MAX_TAGS ? [...t, slug] : t)),
    link, setLink, linkValid: validLink(link),
    visibility,
    setVisibility: (v: Visibility) => { if (v === "everyone" && minor) return; setPicked(true); setVisibility(v); },
    dirty: photos.length > 0 || !!body.trim() || tags.length > 0 || !!link.trim(),
    blocker,
    publish,
    /** Why posting failed, in one sentence. */
    publishProblem: publish.error ? (publish.error instanceof ApiError && publish.error.status === 429 ? "You've posted a lot today. Try again tomorrow." : "Couldn't post that. Check your connection and try again.") : null,
  };
}
