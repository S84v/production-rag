import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// Testing Library cannot auto-register cleanup without Vitest globals, so it is
// wired explicitly here.
afterEach(() => {
  cleanup();
});
