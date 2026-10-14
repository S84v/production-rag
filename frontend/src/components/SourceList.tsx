import type { Source } from "../api";

function getSourceFilename(sourceUri: string): string {
  const path = sourceUri.split("?")[0];
  const filename = path.split("/").filter(Boolean).pop();

  return filename ? decodeURIComponent(filename) : sourceUri;
}

type SourceListProps = {
  sources: Source[];
};

export function SourceList({ sources }: SourceListProps) {
  return (
    <section className="result" aria-labelledby="sources-heading">
      <div className="result-heading">
        <div>
          <h2 id="sources-heading">Sources</h2>
          <p className="result-subheading">
            Retrieved documentation used to generate the answer.
          </p>
        </div>
        <span className="source-count">
          {sources.length} {sources.length === 1 ? "source" : "sources"}
        </span>
      </div>

      <ol className="sources">
        {sources.map((source, index) => (
          <li className="source" key={source.chunk_id}>
            <div className="source-header">
              <div className="source-title">
                <span className="source-number" aria-hidden="true">
                  {index + 1}
                </span>
                <strong>{getSourceFilename(source.source_uri)}</strong>
              </div>
              <span className="score" title="Similarity score">
                {source.score.toFixed(3)}
              </span>
            </div>

            <div className="source-uri">{source.source_uri}</div>

            <div className="source-meta">
              <span>Chunk {source.chunk_index}</span>
              <span>Similarity {source.score.toFixed(3)}</span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
