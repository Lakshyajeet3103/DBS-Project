import { API_BASE } from './config'

/**
 * Sends a query to the RAG backend.
 *
 * The current main.py only reads `message` from the body and has no
 * concept of role or filters yet — extra fields are harmless (FastAPI/
 * pydantic ignores unrecognized ones by default) but are NOT enforced.
 * Sending `role` and `filters` here future-proofs the frontend for
 * when the backend applies them as a hard metadata filter before the
 * vector search runs, per the RBAC design. Until then, treat any
 * "denied" state you see as a UI demo, not real access control.
 */
export async function askDocket({ message, role, filters, signal }) {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User-Role': role,
    },
    body: JSON.stringify({ message, role, filters }),
    signal,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Backend returned ${res.status}: ${text || res.statusText}`)
  }

  const data = await res.json()

  // Normalize the response shape. Current backend returns { reply }.
  // A future RBAC-aware backend might return { reply, citations, denied }.
  return {
    reply: data.reply ?? data.answer ?? '',
    citations: data.citations ?? [],
    denied: Boolean(data.denied),
  }
}
