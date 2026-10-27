/** PUT to the signed storage URL with progress (fetch can't report upload progress, so this is the one XMLHttpRequest in the app). */
export function putWithProgress(url: string, blob: Blob, onProgress: (f: number) => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("PUT", url);
    xhr.setRequestHeader("content-type", blob.type);
    xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
    xhr.onload = () => (xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`upload ${xhr.status}`)));
    xhr.onerror = () => reject(new Error("upload failed"));
    xhr.ontimeout = () => reject(new Error("upload timed out"));
    xhr.timeout = 120_000;
    xhr.send(blob);
  });
}
