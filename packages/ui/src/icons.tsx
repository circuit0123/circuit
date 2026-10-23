import type { SVGProps } from "react";

const paths = {
  home: "M4 11 12 4l8 7v9h-5v-6H9v6H4z",
  map: "M9 4 3 6v14l6-2 6 2 6-2V4l-6 2zM9 4v14M15 6v14",
  briefcase: "M4 8h16v11H4zM9 8V5h6v3M4 13h16",
  users: "M9 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM3 20v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1M17 6a3 3 0 0 1 0 5M21 19v-1a4 4 0 0 0-3-3.8",
  loop: "M8 5h8l4 4v6l-4 4H8l-4-4V9z",
  chart: "M4 20V4M4 20h16M8 16v-5M12 16V8M16 16v-8",
  bell: "M6 17V11a6 6 0 0 1 12 0v6l2 2H4zM10 21h4",
  check: "m5 12 5 5 9-10",
  x: "M6 6l12 12M18 6 6 18",
  pin: "M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11zM12 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4z",
  chevron: "m9 6 6 6-6 6",
  send: "M4 12 20 4l-4 16-4-6z",
  inbox: "M4 13l2-8h12l2 8M4 13v6h16v-6M4 13h5l1 2h4l1-2h5",
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 24, ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75}
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      <path d={paths[name]} />
    </svg>
  );
}
