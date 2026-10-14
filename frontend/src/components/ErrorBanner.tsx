type ErrorBannerProps = {
  message: string;
};

export function ErrorBanner({ message }: ErrorBannerProps) {
  return (
    <div className="error" role="alert">
      <strong>Request failed</strong>
      <span>{message}</span>
    </div>
  );
}
