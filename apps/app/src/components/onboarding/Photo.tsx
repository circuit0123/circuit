"use client";

import { Avatar, Button, Step } from "@circuit/ui";
import { Camera } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { type Flow, photoProblem, useMe } from "@/data";

/** Step 12 (optional). The circuit-pattern avatar is the placeholder until a photo is chosen; Skip is always there. */
export function Photo({ flow }: { flow: Flow }) {
  const me = useMe().data;
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const choose = (f: File | undefined) => {
    if (!f) return;
    const why = photoProblem(f);
    setProblem(why);
    if (why) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
  };

  return (
    <Step
      title="Add a photo."
      subhead="A face helps people say yes to an intro."
      progress={flow.progress}
      onBack={flow.canGoBack ? flow.back : undefined}
      onSkip={flow.saving ? undefined : () => void flow.actions.photo(null)}
      footer={
        <>
          {(problem || flow.error) && <p role="alert" className="t-footnote text-danger">{problem ?? flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={flow.saving || !file} onClick={() => void flow.actions.photo(file)}>Continue</Button>
        </>
      }
    >
      <div className="flex justify-center pt-4">
        <button type="button" onClick={() => input.current?.click()} aria-label={file ? "Choose a different photo" : "Choose a photo"} className="relative rounded-full active:opacity-80">
          <Avatar id={me?.id ?? 0} name={me?.name || "You"} src={preview} size={128} />
          <span className="absolute bottom-1 right-1 flex h-9 w-9 items-center justify-center rounded-full bg-surface-3 text-text" aria-hidden>
            <Camera size={18} strokeWidth={1.75} />
          </span>
        </button>
        <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Photo file" hidden onChange={(e) => { choose(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
    </Step>
  );
}
