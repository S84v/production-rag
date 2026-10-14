import { describe, expect, it } from "vitest";
import indexCss from "./index.css?raw";
import indexHtml from "../index.html?raw";

// The theme now follows the operating system through CSS media queries, so these
// tests assert the mechanism (the stylesheet and document head) rather than a
// JavaScript preference store.
describe("system-controlled theme", () => {
  it("switches the palette with prefers-color-scheme", () => {
    expect(indexCss).toContain("@media (prefers-color-scheme: dark)");
    // The manual override hook must be gone.
    expect(indexCss).not.toContain("[data-theme");
  });

  it("keeps the light palette as the default and dark tokens in the media query", () => {
    const lightRoot = indexCss.indexOf(":root {");
    const darkQuery = indexCss.indexOf("@media (prefers-color-scheme: dark)");

    expect(lightRoot).toBeGreaterThanOrEqual(0);
    expect(lightRoot).toBeLessThan(darkQuery);
    expect(indexCss.slice(darkQuery)).toContain("#0e1716");
  });

  it("lets the browser choose the colour scheme automatically", () => {
    expect(indexCss).toContain("color-scheme: light dark");
  });

  it("declares theme-color metadata for light and dark system preferences", () => {
    expect(indexHtml).toContain('media="(prefers-color-scheme: light)"');
    expect(indexHtml).toContain('media="(prefers-color-scheme: dark)"');
    expect(indexHtml).toContain('content="#f7f5f0"');
    expect(indexHtml).toContain('content="#0e1716"');
  });

  it("neither persists a manual preference nor scripts the theme", () => {
    expect(indexHtml).not.toContain("docassist-theme");
    expect(indexHtml).not.toContain("localStorage");
    expect(indexHtml).not.toContain("matchMedia");
  });
});
