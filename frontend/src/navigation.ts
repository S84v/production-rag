export const VIEWS = [
  { id: "ask", label: "Ask" },
  { id: "about", label: "About" },
  { id: "project", label: "Project" },
] as const;

export type ViewId = (typeof VIEWS)[number]["id"];
