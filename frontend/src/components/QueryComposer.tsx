import type {
  FormEvent,
  KeyboardEvent,
  RefObject,
} from "react";

type QueryComposerProps = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  inputRef: RefObject<HTMLTextAreaElement | null>;
};

export function QueryComposer({
  value,
  onChange,
  onSubmit,
  loading,
  inputRef,
}: QueryComposerProps) {
  const canSubmit = value.trim().length > 0 && !loading;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (canSubmit) {
      onSubmit();
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (canSubmit) {
        onSubmit();
      }
    }
  }

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <label className="composer-label" htmlFor="query">
        Ask a question
      </label>

      <textarea
        id="query"
        ref={inputRef}
        className="composer-input"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="How does dependency injection work in FastAPI?"
        rows={3}
        autoComplete="off"
        disabled={loading}
      />

      <div className="composer-footer">
        <p className="composer-hint">
          Press <kbd>Enter</kbd> to ask, <kbd>Shift</kbd> + <kbd>Enter</kbd> for
          a new line.
        </p>

        <button type="submit" className="composer-submit" disabled={!canSubmit}>
          {loading ? "Generating…" : "Ask question"}
        </button>
      </div>
    </form>
  );
}
