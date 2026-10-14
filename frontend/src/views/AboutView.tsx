export function AboutView() {
  return (
    <div className="view prose-static">
      <header className="hero">
        <p className="eyebrow">About</p>
        <h1>About DocAssist</h1>
        <p className="hero-lead">
          Source-grounded Q&amp;A for technical documentation.
        </p>
      </header>

      <section className="panel">
        <h2>What it does</h2>
        <p>
          DocAssist answers natural-language questions about technical
          documentation. Instead of answering from general knowledge, it
          retrieves the most relevant passages from an indexed documentation
          corpus and asks a language model to answer using only that retrieved
          context.
        </p>
        <p>
          Every answer is returned alongside the documentation sources that were
          used, so you can check the claim against the original text.
        </p>
      </section>

      <section className="panel">
        <h2>How to use it</h2>
        <ol>
          <li>
            Type a question into the composer on the <strong>Ask</strong> view,
            or pick one of the example questions.
          </li>
          <li>
            Press <kbd>Enter</kbd> to submit. Use <kbd>Shift</kbd> +{" "}
            <kbd>Enter</kbd> to add a new line to a longer question.
          </li>
          <li>
            Read the streamed answer, then review the{" "}
            <strong>Sources</strong> list to see which passages were retrieved
            and their similarity scores.
          </li>
        </ol>
      </section>

      <section className="panel">
        <h2>How answers are grounded</h2>
        <p>
          A question is embedded and matched against the indexed documentation.
          The best-matching passages are used to build the context sent to the
          language model, and the same passages are returned to the interface as
          sources. If the retrieved context does not contain the answer, the
          model is expected to say so rather than invent one.
        </p>
      </section>

      <section className="panel">
        <h2>What it indexes today</h2>
        <p>
          The current corpus is the official FastAPI tutorial documentation.
          The product is built to support other documentation collections, but
          only the FastAPI collection is indexed and served in this
          demonstration.
        </p>
      </section>
    </div>
  );
}
