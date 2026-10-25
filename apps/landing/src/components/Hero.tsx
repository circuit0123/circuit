import { Container } from "./Container";

type Props = {
  headline: string;
  subhead: string;
  /** The ONE primary button of the page (or, when a feature is off, the fallback form). */
  action: React.ReactNode;
  /** Home only: the brand video square beside (desktop) or under (phone) the text. */
  media?: React.ReactNode;
  /** Home uses the 64px display size; audience pages (longer headlines) use the 48px one. */
  size?: "display" | "display-sm";
};

/** One headline, one subhead, ONE primary button. */
export function Hero({ headline, subhead, action, media, size = "display-sm" }: Props) {
  return (
    <section aria-label="Introduction">
      <Container className={`grid items-center gap-12 pb-20 pt-12 lg:gap-16 lg:pb-[96px] lg:pt-[96px] ${media ? "lg:grid-cols-[1fr_auto]" : ""}`}>
        <div>
          <h1 className={`${size === "display" ? "t-display" : "t-display-sm"} max-w-[820px] text-balance`}>{headline}</h1>
          <p className="mt-6 max-w-[560px] t-lede text-text-muted">{subhead}</p>
          <div className="mt-10">{action}</div>
        </div>
        {media}
      </Container>
    </section>
  );
}
