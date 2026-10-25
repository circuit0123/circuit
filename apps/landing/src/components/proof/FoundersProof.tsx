import { Example } from "../Example";
import { Proof } from "./Proof";

/** An example of what a founder sees before claiming. Written by us and labelled "Example": no real startup, no numbers. */
export function FoundersProof() {
  return (
    <Proof heading="See who is interested before you claim" lede="We may already list your startup. Claiming it with your company email makes it yours, and shows you which students have looked at it.">
      <Example className="max-w-[540px]">
        <h3 className="t-title2">An agritech startup in Pune</h3>
        <p className="mt-1 t-subhead text-text-muted">Seed stage &middot; Not claimed yet</p>
        <p className="mt-6 t-body">Students have looked at this profile and shown interest in its open roles.</p>
        <p className="mt-3 t-body text-text-muted">Claim it with an email on the company&rsquo;s domain to edit it, post roles and see who is interested.</p>
      </Example>
    </Proof>
  );
}
