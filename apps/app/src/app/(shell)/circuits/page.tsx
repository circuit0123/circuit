import { CircuitsRoute } from "@/components/circuits/CircuitsRoute";

/** The Circuits tab is drawn by the shell's pager; this route owns the URL, and is the 404 screen when the `circuits` flag is off. */
export default function Page() {
  return <CircuitsRoute />;
}
