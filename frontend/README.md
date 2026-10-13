# Folio — role-based knowledge workspace

A new React + Vite frontend for the document assistant. Junior users see Junior documents; Senior users see both collections. Includes login, overview, searchable/filterable library, document reader, text download, per-account bookmarks, assistant with sources, access information, and responsive navigation.

## Run locally

Requires Node.js 18+ and npm. From this folder:

```sh
npm install
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173. The default demo needs no Python server or API key.

| Account | Password |
| --- | --- |
| junior@folio.demo | Junior@123 |
| senior@folio.demo | Senior@123 |

The login page has buttons to fill these credentials. Roles belong to accounts; users cannot select a role after sign-in. Demo authentication is simulated, not a security boundary. All bundled documents are fictional and inspectable in the JavaScript bundle. Never bundle real restricted documents.

Demo chat quotes matching accessible sample passages; it does not call an LLM. Bookmarks persist per account in localStorage. The demo session is in sessionStorage until logout or tab closure. Chat lives in memory and clears on logout or a change of document scope.

## Backend integration

Copy `.env.example` to `.env.local`, set `VITE_DATA_MODE=api`, and leave `VITE_API_BASE_URL` blank for local development. Run the Python backend on port 8000; Vite forwards `/api` requests to it so session cookies work whether you open `localhost:5173` or `127.0.0.1:5173`. Restart Vite after editing these values. For a deployment with a separate API origin, set `VITE_API_BASE_URL` explicitly and configure cookies and CORS for that deployment. See [API_CONTRACT.md](API_CONTRACT.md) for the exact endpoint and response contract.

The existing backend supports `/api/chat` with `{message}` and `{reply}`. This adapter preserves that shape. **Authentication, document APIs, and server-side permissions are still missing in the backend.** Live mode requires those endpoints and never falls back to demo or unrestricted chat. The backend must filter authorized documents before sending context to the LLM. Backend source files have not been changed.

## Verify

```sh
npm test
npm run build
npm run preview -- --host 127.0.0.1
```

Tests cover Junior restrictions, Senior inheritance, deny-by-default access, combined filters, and authorized sample excerpts. Hash routes support direct links on static hosting. Build output is in `dist/` (ignored).

## Source

- `src/App.jsx`: screens, navigation, and session lifecycle
- `src/api.js`: demo/live API adapter and error handling
- `src/access.js`: role checks, filters, and sample retrieval
- `src/data.js`: fictional preview data
- `src/Icons.jsx`, `src/index.css`: visual design
- `tests/access.test.js`: access and retrieval tests

Upload, role administration, and account creation are excluded until responsibilities are assigned. Fonts fall back to system fonts when offline.

The `frontend/` directory is standalone and ready to copy into the frontend repository once its URL is supplied. Do not commit `.env.local`, `node_modules`, or `dist`.
