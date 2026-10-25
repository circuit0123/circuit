import { Example } from "../Example";
import { ShotPlaceholder } from "../Shot";
import { Proof } from "./Proof";

/** The gap map from the partner dashboard, filled with demo data. The dashboard isn't in the app yet, so this is a labelled placeholder: nothing is drawn that the product can't show. */
export function PartnersProof() {
  return (
    <Proof heading="See what your members need, and who can help" lede="A chart and a heatmap of what your members ask for and offer, so a gap such as legal help or fundraising shows up before it costs you a startup. Counts under 5 are hidden.">
      <Example label="Demo data" className="max-w-[720px]">
        <ShotPlaceholder screen="Gap map" wide />
        <p className="mt-4 t-subhead text-text-muted">The gap map on the partner home, shown with demo data.</p>
      </Example>
    </Proof>
  );
}
