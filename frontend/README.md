# DocAssist frontend

The React single-page application for DocAssist. It is a static SPA: it calls the
FastAPI backend's `POST /query` endpoint and renders the streamed answer with its
sources.

## Views

A small header switches between three client-side views (no router):

- **Ask** — question composer, example questions, streamed answer, retrieved
  sources, and timing metrics.
- **About** — what DocAssist does and how answers are grounded.
- **Project** — how it is built, technologies, evaluation, and limitations.

## Configuration

| Variable | Purpose |
| --- | --- |
| `VITE_API_BASE_URL` | Base URL of the backend API (public; baked in at build time) |

When `VITE_API_BASE_URL` is unset, the app calls the relative `/query` path, and
the Vite dev server proxies `/query` to `http://localhost:8000`
(see `vite.config.ts`). For a production build where the frontend and API are on
different origins, set `VITE_API_BASE_URL` to the API origin — for example
`VITE_API_BASE_URL=https://api.example.com npm run build`. Vite inlines `VITE_*`
variables at build time, so the app must be rebuilt when the value changes.

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the Vite dev server (proxies `/query` to the backend) |
| `npm run build` | Type-check (`tsc -b`) and build to `dist/` |
| `npm run preview` | Serve the production build locally |
| `npm run lint` | Run ESLint |
| `npm run test` | Run the Vitest suite once |
| `npm run test:watch` | Run Vitest in watch mode |

## Testing

Tests use **Vitest** with **jsdom** and **React Testing Library**, with the setup
in `src/test/setup.ts`. Run them with `npm test`.

## Deployment

`npm run build` emits `frontend/dist`, which is published to Firebase Hosting
(see `firebase.json`) by the repository's CD workflow. See the repository
[`docs/deployment.md`](../docs/deployment.md) for the deployment details.
