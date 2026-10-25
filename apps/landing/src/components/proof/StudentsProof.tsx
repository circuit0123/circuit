import { ShotPlaceholder } from "../Shot";
import { Proof } from "./Proof";

/** Jobs list and job page screenshots. Those screens aren't in the app yet, so they are labelled placeholders. No role list: there is no public data source to take real roles from. */
export function StudentsProof() {
  return (
    <Proof heading="Roles near you, matched on your skills" lede="Each role shows how well your skills fit it, how far it is, and what it pays. Founders see your skills first, not your college.">
      <div className="grid max-w-[720px] grid-cols-1 gap-8 sm:grid-cols-2">
        <figure>
          <ShotPlaceholder screen="Jobs" />
          <figcaption className="mt-4 t-subhead text-text-muted">Jobs: startups hiring near you, with skill match.</figcaption>
        </figure>
        <figure>
          <ShotPlaceholder screen="Job page" />
          <figcaption className="mt-4 t-subhead text-text-muted">A job page: what the role needs, and your fit for it.</figcaption>
        </figure>
      </div>
    </Proof>
  );
}
