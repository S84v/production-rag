type LogoProps = {
  size?: number;
  className?: string;
};

// The DocAssist mark. The canonical artwork lives in public/favicon.svg and is
// reused here (via its public URL) so the header, favicon, and README share one
// asset.
export function Logo({ size = 28, className }: LogoProps) {
  return (
    <img
      className={className}
      src="/favicon.svg"
      width={size}
      height={size}
      alt=""
      aria-hidden="true"
      decoding="async"
    />
  );
}
