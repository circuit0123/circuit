"use client";
import { useEffect, useId, useRef, type ReactNode } from "react";
import { cx } from "./cx";
import { Icon } from "./icons";

type Props = { open: boolean; onClose: () => void; title: string; children: ReactNode };

/**
 * Shared base for Modal and BottomSheet. Uses the native <dialog>, which traps focus,
 * closes on Esc and returns focus to the opener.
 */
function Dialog({ open, onClose, title, children, className }: Props & { className: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
      className={cx("fade-in m-0 max-w-none bg-transparent p-0 backdrop:bg-ink/40", className)}
    >
      {open && (
        <div className="relative max-h-[85vh] overflow-y-auto bg-surface p-5 shadow-sheet">
          <div className="mb-3 flex items-start justify-between gap-3">
            <h2 id={titleId} className="text-[22px] leading-tight">{title}</h2>
            <button type="button" onClick={onClose} aria-label="Close" className="-m-2 flex h-11 w-11 items-center justify-center rounded-control text-ink-soft hover:bg-line-wash">
              <Icon name="x" />
            </button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}

export function Modal(props: Props) {
  return (
    <Dialog {...props} className="m-auto w-[min(32rem,calc(100vw-2rem))] overflow-hidden rounded-card [&>div]:rounded-card" />
  );
}

export function BottomSheet(props: Props) {
  return (
    <Dialog
      {...props}
      className="sheet-in fixed inset-x-0 bottom-0 top-auto w-full overflow-hidden rounded-t-sheet [&>div]:rounded-t-sheet"
    />
  );
}
