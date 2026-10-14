import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

function streamingResponse(...chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    },
  });

  return { ok: true, body: stream } as unknown as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  window.localStorage.clear();
  fetchMock = vi.fn();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("App navigation", () => {
  it("defaults to the Ask view", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { level: 1, name: "Ask the documentation" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).toHaveAttribute(
      "aria-current",
      "page",
    );
    // The idle state is not a completed empty answer.
    expect(
      screen.queryByText(/did not include an answer/),
    ).not.toBeInTheDocument();
  });

  it("switches views and updates the active state", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "About" }));
    expect(
      screen.getByRole("heading", { level: 1, name: "About DocAssist" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "About" })).toHaveAttribute(
      "aria-current",
      "page",
    );

    await user.click(screen.getByRole("button", { name: "Project" }));
    expect(
      screen.getByRole("heading", { level: 1, name: "How DocAssist is built" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ask" })).not.toHaveAttribute(
      "aria-current",
    );
  });

  it("keeps the composer value when switching away and back", async () => {
    const user = userEvent.setup();
    render(<App />);

    const textarea = screen.getByLabelText("Ask a question");
    await user.type(textarea, "What are path parameters?");

    await user.click(screen.getByRole("button", { name: "Project" }));
    await user.click(screen.getByRole("button", { name: "Ask" }));

    expect(screen.getByLabelText("Ask a question")).toHaveValue(
      "What are path parameters?",
    );
  });

  it("exposes the contact links on every view", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(
      screen.getByRole("link", { name: "LinkedIn" }),
    ).toHaveAttribute("href", "https://www.linkedin.com/in/sarang-dave/");
    expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/S84v",
    );
    expect(screen.getByRole("link", { name: "Email" })).toHaveAttribute(
      "href",
      "mailto:davesarang08@gmail.com",
    );

    await user.click(screen.getByRole("button", { name: "About" }));
    expect(screen.getByRole("link", { name: "GitHub" })).toBeInTheDocument();
  });
});

describe("App example questions", () => {
  it("populates and focuses the composer without submitting", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(
      screen.getByRole("button", {
        name: "How does dependency injection work in FastAPI?",
      }),
    );

    const textarea = screen.getByLabelText("Ask a question");
    expect(textarea).toHaveValue(
      "How does dependency injection work in FastAPI?",
    );
    expect(textarea).toHaveFocus();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("App querying", () => {
  it("streams an answer and renders sources and timings", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      streamingResponse(
        '{"type":"sources","sources":[{"source":"x","source_uri":"filesystem://body.md","chunk_index":8,"chunk_id":"abc","score":0.851}]}\n',
        '{"type":"text","text":"Dependencies are declared with Depends."}\n',
        '{"type":"complete","retrieval_time_ms":25,"total_time_ms":1400}\n',
      ),
    );

    render(<App />);

    await user.type(
      screen.getByLabelText("Ask a question"),
      "How does dependency injection work?",
    );
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(
      await screen.findByText("Dependencies are declared with Depends."),
    ).toBeInTheDocument();
    expect(screen.getByText("body.md")).toBeInTheDocument();
    expect(screen.getByText("Chunk 8")).toBeInTheDocument();
    expect(screen.getByText("Similarity 0.851")).toBeInTheDocument();
    expect(screen.getByText(/1400 ms/)).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/query");
    expect(JSON.parse(String(init.body))).toEqual({
      query: "How does dependency injection work?",
      collection: "fastapi",
      limit: 5,
    });
  });

  it("shows an error when the stream ends without a terminal event", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      streamingResponse('{"type":"text","text":"partial"}\n'),
    );

    render(<App />);

    await user.type(screen.getByLabelText("Ask a question"), "Hello");
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The answer stream ended unexpectedly.",
    );
    // A failed request is not an empty answer.
    expect(
      screen.queryByText(/did not include an answer/),
    ).not.toBeInTheDocument();
  });

  it("shows an empty-answer message when a successful completion has no text", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      streamingResponse(
        '{"type":"sources","sources":[{"source":"x","source_uri":"filesystem://body.md","chunk_index":8,"chunk_id":"abc","score":0.851}]}\n',
        '{"type":"complete","retrieval_time_ms":25,"total_time_ms":1400}\n',
      ),
    );

    render(<App />);

    await user.type(screen.getByLabelText("Ask a question"), "Unanswerable?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(
      await screen.findByText(/did not include an answer to this question/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Generating answer/)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // Sources and timings stay visible alongside the empty-answer message.
    expect(screen.getByText("body.md")).toBeInTheDocument();
    expect(screen.getByText(/1400 ms/)).toBeInTheDocument();
  });

  it("treats a whitespace-only answer as empty", async () => {
    const user = userEvent.setup();
    fetchMock.mockResolvedValue(
      streamingResponse(
        '{"type":"text","text":"   \\n"}\n',
        '{"type":"complete","retrieval_time_ms":10,"total_time_ms":900}\n',
      ),
    );

    render(<App />);

    await user.type(screen.getByLabelText("Ask a question"), "Whitespace?");
    await user.click(screen.getByRole("button", { name: "Ask question" }));

    expect(
      await screen.findByText(/did not include an answer to this question/),
    ).toBeInTheDocument();
  });
});

describe("App theme", () => {
  it("follows the system theme without a manual selector", () => {
    render(<App />);

    expect(screen.queryByRole("radiogroup")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Light" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Dark" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "System" }),
    ).not.toBeInTheDocument();
    expect(document.documentElement).not.toHaveAttribute("data-theme");
    expect(window.localStorage.getItem("docassist-theme")).toBeNull();
  });
});
