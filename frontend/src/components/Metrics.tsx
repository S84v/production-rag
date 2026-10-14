type MetricsProps = {
  retrievalTime: number | null;
  totalTime: number;
};

export function Metrics({ retrievalTime, totalTime }: MetricsProps) {
  return (
    <footer className="metrics" aria-label="Response timing">
      <span>
        <strong>Retrieval</strong> {retrievalTime?.toFixed(0) ?? "—"} ms
      </span>
      <span>
        <strong>Total</strong> {totalTime.toFixed(0)} ms
      </span>
    </footer>
  );
}
