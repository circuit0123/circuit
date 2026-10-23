import { Search } from "lucide-react";
import { cx } from "./cx";

export function SearchField({ className, ...rest }: Omit<React.InputHTMLAttributes<HTMLInputElement>, "type">) {
  return (
    <label className={cx("flex min-h-12 items-center gap-2 rounded-full bg-surface-2 px-4 text-text-muted lg:min-h-11", className)}>
      <Search size={20} strokeWidth={1.75} aria-hidden />
      <input type="search" className="min-w-0 flex-1 bg-transparent t-body text-text outline-none placeholder:text-text-muted" {...rest} />
    </label>
  );
}
