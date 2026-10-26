import { Example } from "../Example";
import { ScreenList } from "../Screens";
import { Proof } from "./Proof";

/** The partner home from the design reference, filled with sample data (the gap map itself has no reference screen yet, so it is not drawn). */
export function PartnersProof() {
  return (
    <Proof heading="See what your members need, and who can help" lede="A chart and a heatmap of what your members ask for and offer, so a gap such as legal help or fundraising shows up before it costs you a startup. Counts under 5 are hidden.">
      <Example label="Demo data" className="max-w-[720px]">
        <ScreenList ids={["partner-home"]} />
      </Example>
    </Proof>
  );
}
