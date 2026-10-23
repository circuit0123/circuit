import { Avatar, BridgeBadge, Button, Card, CircuitLine, VerificationBadge } from "@circuit/ui";
import { Shell } from "@/components/Shell";

// Part 1 preview only: static sample data in the shape of the API. Part 3 replaces it with hooks.
const matches = [
  { name: "Divya Menon", role: "Founder", level: 2, bridge: true, reason: "They offer brand marketing, which you need. Different sector, complementary need." },
  { name: "Dr. Lakshmi Narayanan", role: "Mentor", level: 3, bridge: false, reason: "They offer fundraising advice, which you need, and you are in the same city." },
];

export default function Home() {
  return (
    <Shell banner="Demo — sample data">
      <h1 className="text-[28px] leading-[1.1] tracking-[-0.02em] md:text-[40px]">Good morning, Asha</h1>
      <p className="mt-1 text-ink-soft">One circuit is waiting for your answer.</p>

      <section aria-labelledby="circuit-h" className="mt-6">
        <Card className="p-4 md:p-6">
          <h2 id="circuit-h" className="text-[22px] md:text-[28px]">Your circuit this week</h2>
          <CircuitLine
            className="mt-2"
            title="Circuit loop: Priya offers marketing to you, you offer recruiting to Arjun, Arjun offers fundraising to Priya."
            stations={[
              { label: "Priya", sub: "offers marketing" },
              { label: "You", sub: "offer recruiting", you: true },
              { label: "Arjun", sub: "offers fundraising" },
            ]}
          />
          <p className="mt-3 max-w-[62ch] text-ink-soft">
            Priya helps you with marketing. You help Arjun with recruiting. Answer within 72 hours; if anyone says no, the circuit ends for everyone.
          </p>
          <div className="mt-4 flex gap-3">
            <Button>Accept circuit</Button>
            <Button variant="secondary">Decline</Button>
          </div>
        </Card>
      </section>

      <section aria-labelledby="matches-h" className="mt-10">
        <h2 id="matches-h" className="text-[22px] md:text-[28px]">People who can help</h2>
        <ul className="mt-3 space-y-3">
          {matches.map((m) => (
            <li key={m.name}>
              <Card className="flex gap-3">
                <Avatar name={m.name} />
                <div className="min-w-0">
                  <h3 className="text-lg">{m.name}</h3>
                  <p className="text-sm text-ink-soft">{m.role}</p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <VerificationBadge level={m.level} />
                    {m.bridge && <BridgeBadge />}
                  </div>
                  <p className="mt-2 max-w-[62ch]">{m.reason}</p>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </Shell>
  );
}
