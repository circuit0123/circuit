import { ChevronRight } from "lucide-react";

/** A large tappable row: one answer per tap, no extra Continue (DESIGN.md §4 steps 5 and 6). */
export function ChoiceRow({ label, onClick, disabled, chevron = true }: { label: string; onClick: () => void; disabled?: boolean; chevron?: boolean }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="flex min-h-16 w-full items-center justify-between rounded-card bg-surface px-5 text-left t-body font-medium transition-transform active:scale-[0.98] disabled:opacity-60">
      {label}
      {chevron && <ChevronRight size={16} strokeWidth={2.2} className="text-text-subtle" aria-hidden />}
    </button>
  );
}
