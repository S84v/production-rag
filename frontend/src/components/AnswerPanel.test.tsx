import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { AnswerPanel } from "./AnswerPanel";

describe("AnswerPanel", () => {
  it("renders common markdown constructs", () => {
    const markdown = [
      "## Dependency injection",
      "",
      "Use `Depends` to share logic.",
      "",
      "- reusable",
      "- cached per request",
      "",
      "| Option | Meaning |",
      "| --- | --- |",
      "| gt | greater than |",
      "",
      "```python",
      "def read_items(dep=Depends(get_db)): ...",
      "```",
      "",
      "[FastAPI docs](https://fastapi.tiangolo.com/)",
    ].join("\n");

    const { container } = render(
      <AnswerPanel answer={markdown} loading={false} />,
    );

    expect(
      screen.getByRole("heading", { level: 2, name: "Dependency injection" }),
    ).toBeInTheDocument();
    expect(screen.getByText("reusable")).toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("greater than")).toBeInTheDocument();

    const inlineCode = container.querySelector("p code");
    expect(inlineCode).toHaveTextContent("Depends");

    const block = container.querySelector("pre code");
    expect(block).toHaveTextContent("def read_items");

    const link = screen.getByRole("link", { name: "FastAPI docs" });
    expect(link).toHaveAttribute("href", "https://fastapi.tiangolo.com/");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("does not render raw HTML from the answer", () => {
    const { container } = render(
      <AnswerPanel
        answer={'<script>window.__pwned = true;</script> plain text'}
        loading={false}
      />,
    );

    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText(/plain text/)).toBeInTheDocument();
  });

  it("renders incomplete markdown while streaming without crashing", () => {
    const partial = ["## Results", "", "```python", "def half("].join("\n");

    render(<AnswerPanel answer={partial} loading={true} />);

    expect(
      screen.getByRole("heading", { level: 2, name: "Results" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Streaming");
    expect(screen.getByText(/def half\(/)).toBeInTheDocument();
  });
});
