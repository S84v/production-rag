import { useState } from "react";
import { streamQuery, type Source } from "./api";
import "./App.css";

function App() {
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [retrievalTime, setRetrievalTime] = useState<number | null>(null);
  const [totalTime, setTotalTime] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const trimmedQuery = query.trim();

    if (!trimmedQuery || loading) {
      return;
    }

    setLoading(true);
    setError(null);
    setAnswer("");
    setSources([]);
    setRetrievalTime(null);
    setTotalTime(null);

    try {
      await streamQuery(
        {
          query: trimmedQuery,
          collection: "fastapi",
          limit: 5,
        },
        {
          onEvent: (event) => {
            if (event.type === "sources") {
              setSources(event.sources);
            } else if (event.type === "text") {
              setAnswer((current) => current + event.text);
            } else if (event.type === "complete") {
              setRetrievalTime(event.retrieval_time_ms);
              setTotalTime(event.total_time_ms);
            }
          },
        },
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Something went wrong.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app">
      <header className="header">
        <div className="eyebrow">DOCUMENTATION ASSISTANT</div>
        <h1>Production RAG</h1>
        <p>
          Ask questions about the FastAPI documentation and get answers
          grounded in retrieved sources.
        </p>
      </header>

      <section className="query-card">
        <form className="query-form" onSubmit={handleSubmit}>
          <label htmlFor="query">Ask a question</label>

          <div className="query-row">
            <input
              id="query"
              type="text"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="What is FastAPI?"
              disabled={loading}
              autoComplete="off"
            />

            <button type="submit" disabled={loading || !query.trim()}>
              {loading ? "Generating..." : "Ask"}
            </button>
          </div>

          <p className="query-hint">
            Answers are generated from the indexed FastAPI documentation.
          </p>
        </form>
      </section>

      {error && (
        <div className="error" role="alert">
          <strong>Request failed</strong>
          <span>{error}</span>
        </div>
      )}

      {(answer || loading) && (
        <section className="section answer-section">
          <div className="section-heading">
            <h2>Answer</h2>
            {loading && <span className="status">Streaming</span>}
          </div>

          <div className="answer">
            {answer ? (
              answer
            ) : (
              <span className="answer-placeholder">
                Generating answer...
              </span>
            )}
            {loading && answer && <span className="cursor" aria-hidden="true" />}
          </div>
        </section>
      )}

      {sources.length > 0 && (
        <section className="section sources-section">
          <div className="section-heading">
            <div>
              <h2>Sources</h2>
              <p>Retrieved documentation used to generate the answer.</p>
            </div>

            <span className="source-count">
              {sources.length} {sources.length === 1 ? "source" : "sources"}
            </span>
          </div>

          <div className="sources">
            {sources.map((source, index) => (
              <article className="source" key={source.chunk_id}>
                <div className="source-header">
                  <div className="source-title">
                    <span className="source-number">{index + 1}</span>
                    <strong>{source.source}</strong>
                  </div>

                  <span className="score">
                    {source.score.toFixed(3)}
                  </span>
                </div>

                <div className="source-uri">{source.source_uri}</div>

                <div className="source-meta">
                  <span>Chunk {source.chunk_index}</span>
                  <span>Similarity {source.score.toFixed(3)}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {totalTime !== null && (
        <footer className="metrics">
          <span>
            <strong>Retrieval</strong>{" "}
            {retrievalTime?.toFixed(0) ?? "—"} ms
          </span>
          <span>
            <strong>Total</strong> {totalTime.toFixed(0)} ms
          </span>
        </footer>
      )}
    </main>
  );
}

export default App;
