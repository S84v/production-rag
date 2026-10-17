import { useRef, useState } from "react";
import { streamQuery, type Source } from "./api";
import { AppNav } from "./components/AppNav";
import { Logo } from "./components/Logo";
import type { ViewId } from "./navigation";
import { AboutView } from "./views/AboutView";
import { AskView } from "./views/AskView";
import { ProjectView } from "./views/ProjectView";
import "./App.css";

const CONTACT_LINKS = [
  { label: "LinkedIn", href: "https://www.linkedin.com/in/sarang-dave/" },
  { label: "GitHub", href: "https://github.com/S84v" },
  { label: "Email", href: "mailto:davesarang08@gmail.com" },
];

function App() {
  const [view, setView] = useState<ViewId>("ask");
  const [query, setQuery] = useState("");
  const [answer, setAnswer] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [retrievalTime, setRetrievalTime] = useState<number | null>(null);
  const [totalTime, setTotalTime] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  async function runQuery(rawQuery: string) {
    const trimmedQuery = rawQuery.trim();

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
            } else if (event.type === "error") {
              setError(event.message);
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

  function handleSubmit() {
    void runQuery(query);
  }

  function handleSelectExample(example: string) {
    setQuery(example);
    inputRef.current?.focus();
  }

  return (
    <div className="app">
      <header className="app-header">
        <div className="brand">
          <Logo className="brand-mark" />
          <span className="brand-name">DocAssist</span>
        </div>

        <AppNav view={view} onChange={setView} />
      </header>

      <main className="app-main">
        {view === "ask" && (
          <AskView
            query={query}
            onQueryChange={setQuery}
            onSubmit={handleSubmit}
            onSelectExample={handleSelectExample}
            loading={loading}
            error={error}
            answer={answer}
            sources={sources}
            retrievalTime={retrievalTime}
            totalTime={totalTime}
            inputRef={inputRef}
          />
        )}

        {view === "about" && <AboutView />}
        {view === "project" && <ProjectView />}
      </main>

      <footer className="app-footer">
        <p className="footer-tagline">
          DocAssist — Source-grounded answers from technical documentation.
        </p>

        <ul className="contact" aria-label="Contact">
          {CONTACT_LINKS.map((link) => (
            <li key={link.label}>
              <a href={link.href} target="_blank" rel="noopener noreferrer">
                {link.label}
              </a>
            </li>
          ))}
        </ul>
      </footer>
    </div>
  );
}

export default App;
