import { Example } from "../Example";
import { Proof } from "./Proof";

/** One pick as it looks on Today's picks. Written by us and labelled "Example": no real startup, founder or number. */
export function InvestorsProof() {
  return (
    <Proof heading="A short list, with the reason for each" lede="Each morning you get three startups. They stay the same all day, so there is nothing to refresh and nothing to scroll.">
      <Example className="max-w-[540px]">
        <p className="t-subhead text-text-muted">Today&rsquo;s picks</p>
        <h3 className="mt-1 t-title2">Cold-chain logistics for small retailers</h3>
        <p className="mt-3 flex flex-wrap gap-2">
          {["Logistics", "Seed", "Pune"].map((c) => <span key={c} className="rounded-full bg-surface-2 px-3 py-1 t-subhead text-text">{c}</span>)}
        </p>
        <p className="mt-4 t-body">Fits your focus: logistics, seed stage, within reach of Pune. The founders posted a build log last week and are hiring.</p>
        <p className="mt-3 t-body text-text-muted">The founders have chosen to be seen by investors. You can ask for an introduction, and they decide.</p>
      </Example>
    </Proof>
  );
}
