import { AppShell } from "@/components/AppShell";
import { EnvBanner } from "@/components/EnvBanner";
import { Gate } from "@/components/Gate";

/**
 * Everything signed-in lives under this layout: the environment banner (in every screen the gate can show, so a mock scenario or a
 * persona can always be switched), the gate (sign-in, consent, invite, onboarding), then the shell with its tabs.
 */
export default function ShellLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <EnvBanner />
      <Gate>
        <AppShell>{children}</AppShell>
      </Gate>
    </>
  );
}
