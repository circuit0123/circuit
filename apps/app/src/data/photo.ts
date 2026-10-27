"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { cropAndResize } from "@/lib/image";
import { putWithProgress } from "@/lib/upload";
import { api, unwrap } from "./client";

/** The three calls every image goes through: ask for a signed URL, PUT the file to it, tell the server it is finished. Returns the upload id. */
export async function uploadImage(blob: Blob, purpose: "avatar" | "startup_logo", onProgress: (f: number) => void = () => {}): Promise<number> {
  const up = await unwrap(api.POST("/api/media/uploads", { body: { purpose, content_type: "image/jpeg", size: blob.size } }));
  await putWithProgress(up.upload_url, blob, onProgress);
  await unwrap(api.POST("/api/media/uploads/{upload_id}/complete", { params: { path: { upload_id: up.id } } }));
  return up.id;
}

/**
 * The member's profile photo: a chosen picture is cut square and shrunk on the phone, uploaded, then set (`PUT /api/me/photo`).
 * `remove` goes back to the circuit-pattern avatar.
 */
export function useProfilePhoto() {
  const qc = useQueryClient();
  const refresh = () => qc.invalidateQueries({ queryKey: ["me"] });
  const set = useMutation({
    mutationFn: async (file: File) => {
      const { blob } = await cropAndResize(file, "1:1", { x: 0.5, y: 0.5 });
      const upload_id = await uploadImage(blob, "avatar");
      await unwrap(api.PUT("/api/me/photo", { body: { upload_id } }));
    },
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: () => unwrap(api.DELETE("/api/me/photo")), onSuccess: refresh });
  return { set, remove };
}
