import type { ReactNode } from "react";
import { LineDivider } from "./CircuitLine";

/** Says what will appear here and the one thing to do next. */
export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-card border border-dashed border-rule bg-surface px-5 py-8">
      <LineDivider className="mb-4" />
      <h3 className="text-lg">{title}</h3>
      {children && <p className="mt-1 max-w-[62ch] text-ink-soft">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

/** Error state: what went wrong and how to fix it, with a retry. */
export function ErrorState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div role="alert" className="rounded-card border border-alert bg-surface px-5 py-6">
      <h3 className="text-lg text-alert">Something didn&apos;t load</h3>
      <p className="mt-1 max-w-[62ch]">{message}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
