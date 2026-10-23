import Link from "next/link";
import { Button, EmptyState } from "@circuit/ui";
import { Gate } from "@/components/Gate";
import { AppShell } from "@/components/AppShell";

/** Every destination other than Home is built in a later round; the bar still works. */
export default function Page() {
  return (
    <Gate>
      <AppShell>
        <EmptyState text="This screen isn't built yet. Home is the only one for now." action={<Link href="/"><Button>Back to Home</Button></Link>} />
      </AppShell>
    </Gate>
  );
}
