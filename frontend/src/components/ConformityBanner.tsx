interface ConformityBannerProps {
  reason: string;
}

export function ConformityBanner({ reason }: ConformityBannerProps) {
  return (
    <div className="banner banner-warn" role="alert">
      <strong>Conformity flagged:</strong> {reason}
    </div>
  );
}
