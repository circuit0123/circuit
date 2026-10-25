"use client";

import { LinkButton, type ButtonVariant } from "@circuit/ui/Button";
import { JOIN_LIVE, joinUrl, type Role } from "@/lib/env";
import { chooseRole } from "@/lib/join";
import { useSrc } from "@/lib/src";

type Props = Omit<React.AnchorHTMLAttributes<HTMLAnchorElement>, "href"> & {
  /** The page's own label, e.g. `landing-students`. A valid `?src=` in the page address replaces it. */
  src: string;
  role?: Role;
  /** Looks like a button of this variant. Without it the link is plain (tiles, text links). */
  button?: ButtonVariant;
  /** The form this page opens while the app has no /join screen. Default: the waitlist section (`#waitlist`); /partners uses `partner-form`. */
  form?: "waitlist" | "partner-form";
  /** Always open the form, whatever NEXT_PUBLIC_JOIN_LIVE says (a page whose feature flag is off has no app to go to). */
  toForm?: boolean;
};

/**
 * A call to action. With NEXT_PUBLIC_JOIN_LIVE on it links into the app's join screen with the role pre-set:
 * `APP_URL/join?role=<role>&src=<src>`. Otherwise it is an anchor to the form on the same page (works without JavaScript); a click also
 * remembers the role so the form can preselect it and focus its first field. The look and the label are the same either way.
 */
export function CtaLink({ src, role, button, form = "waitlist", toForm, onClick, children, ...rest }: Props) {
  const href = joinUrl(useSrc(src), role);
  const toTheForm = toForm || !JOIN_LIVE;
  const props = toTheForm
    ? {
        href: `#${form}`,
        onClick: (e: React.MouseEvent<HTMLAnchorElement>) => {
          onClick?.(e);
          const target = document.getElementById(form);
          if (e.defaultPrevented || !target || e.metaKey || e.ctrlKey || e.shiftKey) return;
          // Scroll ourselves (not the browser's fragment jump, which would take focus back from the field the form is about to focus).
          e.preventDefault();
          chooseRole(role);
          target.scrollIntoView({ block: "start", behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
          window.history.replaceState(null, "", `#${form}`);
        },
      }
    : { href, onClick };
  if (button) return <LinkButton variant={button} {...props} {...rest}>{children}</LinkButton>;
  return <a {...props} {...rest}>{children}</a>;
}
