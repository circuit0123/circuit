/**
 * Photos are cut and shrunk on the phone before upload (DESIGN.md §11, PRODUCTION.md §14): cropped to the build log's frame, long side
 * at most 1440px, re-encoded as JPEG. That saves the member's data, keeps under the 5 MB limit, drops EXIF (location) on the way, and
 * turns an iPhone HEIC the browser can read into something the server takes. The server compresses again anyway.
 */
export const MAX_SIDE = 1440;
export type Aspect = "4:5" | "1:1";
const RATIO: Record<Aspect, number> = { "4:5": 4 / 5, "1:1": 1 };

/** The frame a picture starts in: square for landscape and square photos, 4:5 for portrait ones (DESIGN.md §4 Build log). */
export const aspectFor = (w: number, h: number): Aspect => (w / h > 0.9 ? "1:1" : "4:5");

/** The part of a w×h picture that the frame keeps: the largest rectangle of the frame's shape, placed by `focus` (0–1 each way). */
export function cropRect(w: number, h: number, aspect: Aspect, focus: { x: number; y: number }) {
  const r = RATIO[aspect];
  if (w / h > r) {
    const cw = h * r;
    return { x: (w - cw) * focus.x, y: 0, w: cw, h };
  }
  const ch = w / r;
  return { x: 0, y: (h - ch) * focus.y, w, h: ch };
}

/** Reads a picture's size. Throws when the browser can't decode it (HEIC outside Safari, a broken file). */
export async function imageSize(file: Blob): Promise<{ width: number; height: number }> {
  const bmp = await createImageBitmap(file);
  const out = { width: bmp.width, height: bmp.height };
  bmp.close();
  return out;
}

/** Crops to the frame and shrinks to MAX_SIDE. Returns a JPEG and its size. */
export async function cropAndResize(file: Blob, aspect: Aspect, focus: { x: number; y: number }): Promise<{ blob: Blob; width: number; height: number }> {
  const bmp = await createImageBitmap(file);
  try {
    const c = cropRect(bmp.width, bmp.height, aspect, focus);
    const scale = Math.min(1, MAX_SIDE / Math.max(c.w, c.h));
    const width = Math.max(1, Math.round(c.w * scale));
    const height = Math.max(1, Math.round(c.h * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("no canvas");
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(bmp, c.x, c.y, c.w, c.h, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.86));
    if (!blob) throw new Error("encode failed");
    return { blob, width, height };
  } finally {
    bmp.close();
  }
}
