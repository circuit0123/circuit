import { Gate } from "@/components/Gate";
import { AppShell } from "@/components/AppShell";

/** Everything signed-in lives under this layout: the gate (sign-in, consent, invite, onboarding), then the shell with its tabs. */
export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <Gate>
      <AppShell>{children}</AppShell>
    </Gate>
  );
}
