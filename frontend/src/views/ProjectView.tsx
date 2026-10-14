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
          indexes one collection — the official FastAPI tutorial documentation —
          and the API only serves collections that appear on a fixed allowlist.
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
          Generation quality is assessed by capturing full end-to-end answers for
          the same question set and reviewing them against reference answers and
          the retrieved sources. The anchor-based retrieval baseline is still
          pending a recorded run, so no retrieval metrics are published here.
        </p>
      </section>

      <section className="panel">
        <h2>Limitations</h2>
        <ul>
          <li>
            Deployment is not configured in the repository; the container image
            is built and run locally.
          </li>
          <li>
            The request rate limit is held in memory per instance, so it is not a
            global limit across multiple running instances.
          </li>
          <li>
            The embedding model is loaded lazily and cached per process, and must
            be available locally.
          </li>
          <li>
            Only the FastAPI tutorial subset is indexed; answers outside that
            corpus are unsupported.
          </li>
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
