export function ProjectView() {
  return (
    <div className="view prose-static">
      <header className="hero">
        <p className="eyebrow">Project</p>
        <h1>How DocAssist is built</h1>
        <p className="hero-lead">
          A small, deliberately scoped retrieval-augmented generation system.
        </p>
      </header>

      <section className="panel">
        <h2>Architecture</h2>
        <p>
          DocAssist is a Retrieval-Augmented Generation (RAG) service. A FastAPI
          backend exposes a streaming query endpoint, PostgreSQL is the
          authoritative store for document metadata and chunk text, and Qdrant
          stores the vector embeddings used for similarity search. A React
          single-page application provides the interface.
        </p>
        <p>
          Storage and retrieval are scoped by collection. This demonstration
          indexes one collection — the official FastAPI documentation — and the
          API only serves collections that appear on a fixed allowlist.
        </p>
      </section>

      <section className="panel">
        <h2>Retrieval and generation flow</h2>
        <ol>
          <li>
            Markdown documents are ingested, hashed for idempotency, and split
            into structure-aware chunks that preserve headings and code blocks.
          </li>
          <li>
            Chunks are embedded with a Sentence Transformers model and written to
            Qdrant, while their text and metadata live in PostgreSQL.
          </li>
          <li>
            A question is embedded, matched against Qdrant, and the winning
            points are hydrated from PostgreSQL.
          </li>
          <li>
            The retrieved passages form the context for a DeepSeek generation
            request, and the answer is streamed back to the client as newline
            delimited JSON events.
          </li>
        </ol>
      </section>

      <section className="panel">
        <h2>Technologies</h2>
        <ul className="chip-list">
          <li>FastAPI</li>
          <li>PostgreSQL</li>
          <li>Qdrant</li>
          <li>Sentence Transformers</li>
          <li>DeepSeek</li>
          <li>React</li>
          <li>TypeScript</li>
          <li>Vite</li>
          <li>Alembic</li>
          <li>OpenTelemetry</li>
          <li>Docker Compose</li>
        </ul>
      </section>

      <section className="panel">
        <h2>Evaluation</h2>
        <p>
          Retrieval quality is measured against a labelled question set whose
          labels are content anchors — verbatim excerpts tied to a source
          document — rather than runtime chunk identifiers, so the dataset stays
          reproducible across re-chunking.
        </p>
        <p>
          The recorded offline retrieval baseline covers 29 examples with no
          reranker. At the default depth of five it reports precision 0.13,
          recall 0.60, hit rate 0.66, and MRR 0.53 — offline evaluation numbers,
          not live production or answer-quality metrics.
        </p>
        <p>
          Generation quality is assessed separately by capturing full end-to-end
          answers for the same question set and reviewing them against the
          reference answers and the retrieved sources; those generation artifacts
          predate the current corpus and are historical.
        </p>
      </section>

      <section className="panel">
        <h2>Limitations</h2>
        <ul>
          <li>
            Only the official FastAPI documentation collection is indexed and
            served; there is no upload or collection-selection interface.
          </li>
          <li>
            The request rate limit is held in memory per instance, so it is not a
            global limit across multiple running instances.
          </li>
          <li>
            The embedding model is loaded lazily and cached per process, so the
            first query after a cold start pays the load cost.
          </li>
          <li>Retrieval uses a single bi-encoder ranking with no reranker.</li>
          <li>
            Hosted database and vector-store endpoints are configurable, but
            account, quota, and billing state are not verified by the
            application.
          </li>
        </ul>
      </section>
    </div>
  );
}
