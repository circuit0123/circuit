import { cx } from "@circuit/ui/cx";

/** The page column: 1120px (760px for narrow text sections) with 16px side padding on a phone and 24px on desktop. */
export function Container({ narrow, className, ...rest }: React.HTMLAttributes<HTMLDivElement> & { narrow?: boolean }) {
  return <div className={cx("mx-auto w-full px-4 lg:px-6", narrow ? "max-w-[808px]" : "max-w-[1168px]", className)} {...rest} />;
}
