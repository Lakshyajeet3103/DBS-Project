# Backend integration contract

These endpoints are expected in `VITE_DATA_MODE=api`. Only `POST /api/chat` exists in the supplied backend today. This document describes remaining integration work, not implemented backend functionality.

## Session

All requests use `credentials: include`. Use a server-issued HttpOnly cookie (Secure in HTTPS deployments), appropriate SameSite settings, server-side session expiration, and CSRF protection/origin validation for mutations. Allow the explicit frontend origin in CORS and enable credentials. Use the same hostname for both local services, e.g. `127.0.0.1:5173` and `127.0.0.1:8000`.

- `POST /api/auth/login`: body `{ "email": "...", "password": "..." }`; set the cookie and return the user below. Invalid credentials: 401.
- `GET /api/auth/me`: return the authenticated user, or 401.
- `POST /api/auth/logout`: revoke the session, clear the cookie, return 204.

```json
{ "id": "user-123", "name": "Alex Morgan", "email": "alex@example.com", "role": "junior" }
```

Roles must be exactly `junior` or `senior` and assigned by the server. Never trust a role in a request body. Unsupported roles fail closed in the frontend. A 401 during a protected request returns the UI to login. No production passwords or bearer tokens are stored by the frontend.

## Documents

- `GET /api/documents`: an array of authorized document metadata. Junior gets only Junior items; Senior gets both. No pagination is assumed in this first interface.
- `GET /api/documents/:id`: one authorized document with `content`. Return 403 or 404 when inaccessible. Direct links require the same server authorization as listings.

```json
{
  "id": "team-handbook",
  "title": "The team handbook",
  "description": "Our everyday working principles.",
  "category": "People & culture",
  "type": "Policy",
  "year": "2026",
  "level": "junior",
  "date": "2026-10-04",
  "minutes": 8,
  "author": "People & Culture",
  "content": "Heading\n\nDocument text."
}
```

Use stable URL-safe IDs and ISO `YYYY-MM-DD` dates. `content` is required in detail responses and optional in listings. The reader renders plain text, never injected HTML. Download exports authorized text rather than the original PDF. Bookmarks are per-user browser preferences and are not server-synchronized.

## Assistant

`POST /api/chat` receives:

```json
{ "message": "How do project reviews work?", "document_id": "team-handbook" }
```

`document_id` is optional. Return:

```json
{
  "reply": "Answer grounded in authorized document context.",
  "sources": [{ "id": "team-handbook", "title": "The team handbook" }]
}
```

The existing `{message}` / `{reply}` shape is supported. `sources` is optional. Authenticate every chat request and filter vector retrieval by the role in the server session BEFORE context reaches the LLM. Validate any document scope and restrict retrieval to it; never silently ignore a restricted scope. The frontend filters source links against the authorized library, but only the server can prevent restricted content entering an answer.

Each question is currently independent, matching the existing backend. Visible chat history is not sent as LLM memory. Requests time out after 60 seconds. Failures display a safe message and restore the question to the composer for manual retry.

## Backend acceptance checks

1. A Junior session cannot fetch any Senior document using a guessed ID.
2. Search and chat cannot expose Senior-only facts to Juniors.
3. Senior sessions can retrieve both levels.
4. Editing browser storage, request bodies, or URLs cannot elevate a server session.
5. Logout and expiration invalidate all protected requests.
6. Wrong-origin mutations are rejected.

Demo login and frontend route guards are presentation behavior, not server security. Live mode has no silent demo or unauthenticated fallback.
