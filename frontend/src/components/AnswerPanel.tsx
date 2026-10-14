import { useDeferredValue } from "react";
import Markdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  // Links open in a new tab; react-markdown escapes raw HTML by default, so no
  // aria-hidden or unsafe markup can slip through.
  a: ({ href, title, children }) => (
    <a
      href={href}
      title={title}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
    </a>
  ),
  // Wrap tables so they can scroll horizontally instead of breaking the layout.
  table: ({ children }) => (
    <div className="table-scroll">
      <table>{children}</table>
    </div>
  ),
};

type AnswerPanelProps = {
  answer: string;
  loading: boolean;
};

const EMPTY_ANSWER_MESSAGE =
  "The documentation did not include an answer to this question. Try rephrasing it or asking about a related topic.";

export function AnswerPanel({ answer, loading }: AnswerPanelProps) {
  // Defer the re-parse of streaming text so token updates never block typing.
  const deferredAnswer = useDeferredValue(answer);
  const hasContent = deferredAnswer.trim().length > 0;

  return (
    <section className="result" aria-labelledby="answer-heading">
      <div className="result-heading">
        <h2 id="answer-heading">Answer</h2>
        {loading && (
          <span className="status" role="status">
            Streaming
          </span>
        )}
      </div>

      <div className="answer" aria-busy={loading}>
        {/* The answer box spans the full composer width; .prose constrains only
            the answer content to a comfortable reading measure. */}
        <div className="prose">
          {hasContent ? (
            <>
              <Markdown remarkPlugins={[remarkGfm]} components={components}>
                {deferredAnswer}
              </Markdown>
              {loading && <span className="cursor" aria-hidden="true" />}
            </>
          ) : loading ? (
            <p className="answer-placeholder">Generating answer…</p>
          ) : (
            // Rendered only for a completed request with no answer text; AskView
            // gates the other result states.
            <p className="answer-empty">{EMPTY_ANSWER_MESSAGE}</p>
          )}
        </div>
      </div>
    </section>
  );
}
