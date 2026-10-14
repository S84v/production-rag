import { VIEWS, type ViewId } from "../navigation";

type AppNavProps = {
  view: ViewId;
  onChange: (view: ViewId) => void;
};

export function AppNav({ view, onChange }: AppNavProps) {
  return (
    <nav className="nav" aria-label="Primary">
      {VIEWS.map((item) => {
        const active = item.id === view;

        return (
          <button
            key={item.id}
            type="button"
            className={`nav-tab${active ? " nav-tab--active" : ""}`}
            aria-current={active ? "page" : undefined}
            onClick={() => onChange(item.id)}
          >
            {item.label}
          </button>
        );
      })}
    </nav>
  );
}
