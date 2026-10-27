import { ScreenList } from "../Screens";
import { Proof } from "./Proof";

/** The Jobs list, the map and a job page, rendered from the design reference with sample data. No role list: there is no public data source to take real roles from. */
export function StudentsProof() {
  return (
    <Proof heading="Roles near you, matched on your skills" lede="Each role shows how well your skills fit it, how far it is, and what it pays. Founders see your skills first, not your college.">
      <ScreenList ids={["discover-jobs", "map", { id: "job", caption: "A job page: what it pays, what it needs, and your fit. Apply with your profile in one tap; founders see applicants ranked by skill match, not by college." }]} />
    </Proof>
  );
}
