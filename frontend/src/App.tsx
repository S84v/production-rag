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
        <h1>Production RAG</h1>
        <p>Ask questions about the FastAPI documentation.</p>
      </header>

      <form className="query-form" onSubmit={handleSubmit}>
        <label htmlFor="query">Question</label>

        <div className="query-row">
          <input
            id="query"
            type="text"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="What is FastAPI?"
            disabled={loading}
          />

          <button type="submit" disabled={loading || !query.trim()}>
            {loading ? "Generating..." : "Ask"}
          </button>
        </div>
      </form>

      {error && <div className="error">{error}</div>}

      {(answer || loading) && (
        <section className="answer-section">
          <h2>Answer</h2>
          <div className="answer">
            {answer || "Generating answer..."}
          </div>
        </section>
      )}

      {sources.length > 0 && (
        <section className="sources-section">
          <h2>Sources</h2>

          <div className="sources">
            {sources.map((source) => (
              <article className="source" key={source.chunk_id}>
                <div className="source-header">
                  <strong>{source.source}</strong>
                  <span>Score: {source.score.toFixed(3)}</span>
                </div>

                <div>{source.source_uri}</div>
                <div>Chunk {source.chunk_index}</div>
              </article>
            ))}
          </div>
        </section>
      )}

      {totalTime !== null && (
        <footer className="metrics">
          <span>
            Retrieval: {retrievalTime?.toFixed(0) ?? "—"} ms
          </span>
          <span>Total: {totalTime.toFixed(0)} ms</span>
        </footer>
      )}
    </main>
  );
}

export default App;
