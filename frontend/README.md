# Marginalia — Study Assistant Frontend

A React + Vite chat UI for the FastAPI/RAG backend.

## Run it

```bash
npm install
npm run dev
```

This starts the dev server on **http://localhost:5173** — matching the
`allow_origins` already configured in your FastAPI backend's CORS middleware.

Make sure the backend is running separately:

```bash
uvicorn main:app --reload
```

The frontend expects the backend at `http://127.0.0.1:8000`. If your backend
runs elsewhere, change `API_BASE` at the top of `src/App.jsx`.

## What's here

- `src/App.jsx` — chat UI: message thread, composer, connection status
- `src/index.css` — design system (colors, type, layout)
- Talks to `POST /api/chat` with `{ "message": string }`, expects `{ "reply": string }` back
