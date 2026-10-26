import { LANDING_URL } from "@/lib/env";

/** Terms and Privacy Policy live on the landing site; without its address (dev) they are plain underlined words. */
export function LegalLink({ path, children }: { path: "/terms" | "/privacy"; children: React.ReactNode }) {
  return LANDING_URL ? (
    <a href={`${LANDING_URL}${path}`} target="_blank" rel="noopener noreferrer" className="underline">{children}</a>
  ) : (
    <span className="underline">{children}</span>
  );
}

export function Legal() {
  return (
    <p className="t-footnote text-center text-text-muted">
      By continuing you agree to the <LegalLink path="/terms">Terms</LegalLink> and <LegalLink path="/privacy">Privacy Policy</LegalLink>.
    </p>
  );
}
