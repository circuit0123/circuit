import type { ReactNode } from "react";
import { cx } from "./cx";
import { Icon } from "./icons";

function Pill({ className, children }: { className: string; children: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-sm font-semibold", className)}>
      {children}
    </span>
  );
}

const verification: Record<1 | 2 | 3, string> = {
  1: "Email verified",
  2: "Work email verified",
  3: "Verified by Circuit",
};

export function VerificationBadge({ level }: { level: number }) {
  if (level < 1) return null;
  const l = Math.min(3, Math.round(level)) as 1 | 2 | 3;
  return (
    <Pill className="bg-verified text-white">
      <Icon name="check" size={14} strokeWidth={2.5} />
      {verification[l]}
    </Pill>
  );
}

export function BridgeBadge() {
  return <Pill className="bg-bridge text-white">Bridge match</Pill>;
}

export function HiringBadge({ roles }: { roles?: number }) {
  return (
    <Pill className="bg-signal text-ink">
      {roles ? `Hiring: ${roles} ${roles === 1 ? "role" : "roles"}` : "Hiring"}
    </Pill>
  );
}

export function StatusBadge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "bad" }) {
  const tones = { neutral: "bg-line-wash text-ink", good: "bg-verified text-white", bad: "bg-alert text-white" };
  return <Pill className={tones[tone]}>{children}</Pill>;
}
