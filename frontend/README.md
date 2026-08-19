# Docket — frontend

Vite + React chat UI for the DBS-Project RAG backend (`main.py`). Designed
around the RBAC/citation/grounding requirements: a role switcher, document
metadata filters, citation chips on every answer, and a distinct "redacted"
state for anything outside the active role's clearance.

## Run it

```bash
cd frontend
npm install
cp .env.example .env   # points at http://localhost:8000 by default
npm run dev
```

This starts on `http://localhost:5173`, which matches the CORS origins
already allowed in `main.py`. Run the FastAPI backend separately:

```bash
uvicorn main:app --reload
```

## What's wired up vs. what still needs backend work

The current `main.py` only accepts `{ "message": "..." }` on `POST
/api/chat` and returns `{ "reply": "..." }`. This frontend already sends
`role` and `filters` on every request (see `src/api.js`), and knows how to
render `citations` and a `denied` flag if the backend returns them — but
**today those fields are ignored server-side**, so a "Junior Analyst" can
still technically retrieve anything the backend's retriever returns.

To make the RBAC/grounding claims true end-to-end, the backend needs:

1. **Metadata on ingest** (`ingest.py`) — tag each chunk with the schema
   from the spec (`document_title`, `document_type`, `section_id`,
   `effective_year`, plus a `clearance` level: 1 = general policy,
   2 = manager-level contracts, 3 = executive compensation).
2. **A hard filter before vector search** — in `main.py`, build a Chroma
   `where` clause from the request's `role` (mapped to a max `clearance`)
   and `filters` (`document_type`, `effective_year`), and pass it to
   `retriever` / `vector_db.similarity_search(..., filter=where)`. This is
   what makes it a database-level control instead of a UI-level one.
3. **Citations + refusal in the response** — update the prompt to require
   `section_id` per claim and the exact refusal string, then parse/return
   `{ reply, citations, denied }` instead of just `{ reply }`.

Until step 2 lands, treat the role switcher here as a **demo of the UX**,
not an access control boundary — anyone hitting the API directly bypasses
it. `src/config.js` has a comment flagging this same thing.

## Structure

```
src/
  api.js               fetch wrapper for POST /api/chat
  config.js             roles, clearance levels, doc types, years
  styles.css             design tokens + layout
  App.jsx                 state, thread, composer
  components/
    Sidebar.jsx           role switcher + metadata filters
    MessageEntry.jsx       chat bubble / citation card / redaction state
```
