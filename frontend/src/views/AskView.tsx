import type { RefObject } from "react";
import type { Source } from "../api";
import { AnswerPanel } from "../components/AnswerPanel";
import { ErrorBanner } from "../components/ErrorBanner";
import { Metrics } from "../components/Metrics";
import { QueryComposer } from "../components/QueryComposer";
import { SourceList } from "../components/SourceList";

// Curated to match the ingested FastAPI tutorial docs (path/query parameters,
// request bodies, response models and status codes, dependency injection, error
// handling, middleware, and security).
const EXAMPLE_QUESTIONS = [
  "How does dependency injection work in FastAPI?",
  "What is the difference between path and query parameters?",
  "How do I define a request body with a Pydantic model?",
  "How do I customize the status code of a response?",
  "How do I raise an HTTP error in a path operation?",
  "How does FastAPI handle authentication with OAuth2 and JWT?",
];

type AskViewProps = {
  query: string;
  onQueryChange: (value: string) => void;
  onSubmit: () => void;
  onSelectExample: (value: string) => void;
  loading: boolean;
  error: string | null;
  answer: string;
  sources: Source[];
  retrievalTime: number | null;
  totalTime: number | null;
  inputRef: RefObject<HTMLTextAreaElement | null>;
};

export function AskView({
  query,
  onQueryChange,
  onSubmit,
  onSelectExample,
  loading,
  error,
  answer,
  sources,
  retrievalTime,
  totalTime,
  inputRef,
}: AskViewProps) {
  const hasAnswerText = answer.trim().length > 0;
  // Only a completed request with no answer text is an "empty answer"; the idle
  // state (no totalTime) and failures (error set) are excluded.
  const showEmptyAnswer =
    !loading && totalTime !== null && !hasAnswerText && error === null;
  const showAnswer = loading || hasAnswerText || showEmptyAnswer;
  const showExamples = !loading && !hasAnswerText;
  const announcement = loading
    ? "Generating answer…"
    : showEmptyAnswer
      ? "No answer found in the documentation."
      : totalTime !== null
        ? "Answer complete."
        : "";

  return (
    <div className="view view--ask">
      <header className="hero">
        <p className="eyebrow">FastAPI documentation</p>
        <h1>Ask the documentation</h1>
        <p className="hero-lead">
          Answers are grounded in the official FastAPI documentation and include
          inspectable sources you can trace back to the original text.
        </p>
      </header>

      <QueryComposer
        value={query}
        onChange={onQueryChange}
        onSubmit={onSubmit}
        loading={loading}
        inputRef={inputRef}
      />

      {showExamples && (
        <section className="examples" aria-labelledby="examples-heading">
          <h2 id="examples-heading" className="examples-heading">
            Try an example
          </h2>
          <ul className="example-list">
            {EXAMPLE_QUESTIONS.map((question) => (
              <li key={question}>
                <button
                  type="button"
                  className="example"
                  onClick={() => onSelectExample(question)}
                >
                  {question}
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}

      {error && <ErrorBanner message={error} />}

      {showAnswer && <AnswerPanel answer={answer} loading={loading} />}

      {sources.length > 0 && <SourceList sources={sources} />}

      {totalTime !== null && (
        <Metrics retrievalTime={retrievalTime} totalTime={totalTime} />
      )}

      <p className="sr-only" role="status">
        {announcement}
      </p>
    </div>
  );
}
