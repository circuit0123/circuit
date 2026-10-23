import { CircuitLine } from "@circuit/ui";

const APP_URL = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";

export default function Home() {
  return (
    <main id="main">
      <header className="mx-auto flex max-w-[1120px] items-center justify-between px-4 py-4 md:px-8">
        <span className="font-display text-xl font-extrabold">Circuit</span>
        <a href={APP_URL} className="inline-flex min-h-11 items-center rounded-control px-3 font-semibold text-line hover:bg-line-wash">
          Sign in
        </a>
      </header>

      <section className="mx-auto grid max-w-[1120px] items-center gap-8 px-4 pb-16 pt-6 md:grid-cols-[1.1fr_1fr] md:gap-12 md:px-8 md:pb-24 md:pt-16">
        <div>
          <h1 className="font-display text-[40px] font-extrabold leading-[1.02] tracking-[-0.02em] md:text-[72px]">
            Need a hand? Someone nearby has it.
          </h1>
          <p className="mt-5 max-w-[46ch] text-lg text-ink-soft">
            Circuit matches students, founders and mentors on what each needs and can offer, not on job titles or college names.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href={APP_URL} className="inline-flex min-h-11 items-center rounded-control bg-line px-5 font-semibold text-white hover:bg-[#1a3fb8]">
              Open Circuit
            </a>
            <a href="#circuits" className="inline-flex min-h-11 items-center rounded-control border border-rule bg-surface px-5 font-semibold hover:border-ink-soft">
              See how a circuit works
            </a>
          </div>
        </div>

        <figure id="circuits" className="rounded-card border border-rule bg-surface p-4 md:p-6">
          <CircuitLine
            animate
            title="A circuit of three people: Priya offers marketing to Asha, Asha offers recruiting to Arjun, Arjun offers fundraising help to Priya."
            stations={[
              { label: "Priya", sub: "offers marketing" },
              { label: "Asha", sub: "offers recruiting" },
              { label: "Arjun", sub: "offers fundraising" },
            ]}
          />
          <figcaption className="mt-3 max-w-[56ch] text-sm text-ink-soft">
            An example circuit. Priya&apos;s marketing helps Asha, Asha&apos;s recruiting helps Arjun, and Arjun&apos;s fundraising help comes back to Priya. Nobody needs a one-to-one swap.
          </figcaption>
        </figure>
      </section>
    </main>
  );
}
