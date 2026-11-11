/** ui_v2 on the landing site (docs/ui-v2-plan.md §1). `off`: the v2 home does not exist. `preview`: it is built at the hidden, no-index /next/. `on`: it is `/`. */
const raw = process.env.NEXT_PUBLIC_UI_V2;
export const UI_V2_MODE = raw === "on" || raw === "preview" ? raw : "off";
export const UI_V2_ON = UI_V2_MODE === "on";
