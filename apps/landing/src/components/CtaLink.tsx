"use client";

import { LinkButton, type ButtonVariant } from "@circuit/ui/Button";
import { joinUrl, type Role } from "@/lib/env";
import { useSrc } from "@/lib/src";

type Props = Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  /** The page's own label, e.g. `landing-students`. A valid `?src=` in the page address replaces it. */
  src: string;
  role?: Role;
  /** Looks like a button of this variant. Without it the link is plain (tiles, text links). */
  button?: ButtonVariant;
};

/** A link into the app's join screen with the role pre-set: `APP_URL/join?role=<role>&src=<src>`. */
export function CtaLink({ src, role, button, children, ...rest }: Props) {
  const href = joinUrl(useSrc(src), role);
  if (button) return <LinkButton variant={button} href={href} {...rest}>{children}</LinkButton>;
  return <a href={href} {...rest}>{children}</a>;
}
