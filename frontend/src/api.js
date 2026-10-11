import { accounts, documents } from './data';
import { canAccess, findExcerpts, validRole } from './access';
export const DEMO = import.meta.env.VITE_DATA_MODE !== 'api';
const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');
const SESSION_KEY = 'folio-demo-session';
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}
async function request(path, options = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(`${BASE}${path}`, {
      ...options,
      credentials: 'include',
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      }
    });
    if (!response.ok) {
      // Probe endpoints expect 401 when logged out; only force re-login for real session loss.
      const authProbe = path === '/api/auth/login' || path === '/api/auth/me';
      if (response.status === 401 && !authProbe) window.dispatchEvent(new Event('folio:session-expired'));
      const messages = {
        401: 'Your session has expired. Please sign in again.',
        403: 'You do not have permission to access this content.',
        404: 'This resource is not available on the backend yet.',
        429: 'Too many requests. Please wait a moment and try again.'
      };
      throw new ApiError(path === '/api/auth/login' && response.status === 401 ? 'The email or password is incorrect.' : messages[response.status] || 'The server could not complete your request. Please try again.', response.status);
    }
    return response.status === 204 ? null : await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(error.name === 'AbortError' ? 'The request timed out. Please try again.' : 'Cannot reach the backend. Check that it is running and try again.', 0);
  } finally {
    clearTimeout(timeout);
  }
}
function publicUser(account) {
  if (!account || !validRole(account.role) || !account.id || !account.name || !account.email) throw new ApiError('The account has no supported access level. Contact your team lead.', 403);
  return {
    id: account.id,
    name: account.name,
    email: account.email,
    role: account.role
  };
}
export const api = {
  async session() {
    if (DEMO) {
      const account = accounts.find(item => item.id === sessionStorage.getItem(SESSION_KEY));
      return account ? publicUser(account) : null;
    }
    try {
      return publicUser(await request('/api/auth/me'));
    } catch (error) {
      if (error.status === 401) return null;
      throw error;
    }
  },
  async login(email, password) {
    if (DEMO) {
      const account = accounts.find(item => item.email === email.trim().toLowerCase() && item.password === password);
      if (!account) throw new ApiError('The email or password is incorrect. Use one of the demo accounts below.', 401);
      sessionStorage.setItem(SESSION_KEY, account.id);
      return publicUser(account);
    }
    return publicUser(await request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({
        email: email.trim(),
        password
      })
    }));
  },
  async logout() {
    if (DEMO) sessionStorage.removeItem(SESSION_KEY);else await request('/api/auth/logout', {
      method: 'POST'
    });
  },
  async documents(user) {
    const data = DEMO ? documents : await request('/api/documents');
    if (!Array.isArray(data)) throw new ApiError('The document response is not in the expected format.', 502);
    return data.filter(doc => canAccess(user, doc));
  },
  async document(id, user) {
    const doc = DEMO ? documents.find(item => item.id === id) : await request(`/api/documents/${encodeURIComponent(id)}`);
    if (!doc || !canAccess(user, doc)) throw new ApiError('This document is unavailable or outside your access level.', 403);
    return doc;
  },
  async chat(message, user, documentId) {
    if (!DEMO) {
      // The server derives the role from the authenticated session, never this client.
      const data = await request('/api/chat', {
        method: 'POST',
        body: JSON.stringify({
          message,
          ...(documentId ? {
            document_id: documentId
          } : {})
        })
      });
      if (typeof data?.reply !== 'string') throw new ApiError('The assistant returned an unexpected response. Please try again.', 502);
      return {
        reply: data.reply,
        sources: Array.isArray(data.sources) ? data.sources : []
      };
    }
    const allowed = documents.filter(doc => canAccess(user, doc) && (!documentId || doc.id === documentId));
    const excerpts = findExcerpts(allowed, message);
    return {
      reply: excerpts.length ? 'Here are matching passages from your sample documents:\n\n' + excerpts.map(hit => hit.text).join('\n\n') : 'I couldn’t find a matching passage in your accessible sample documents. Try asking about onboarding, security, project reviews, or working hours.',
      sources: [...new Map(excerpts.map(hit => [hit.id, {
        id: hit.id,
        title: hit.title
      }])).values()]
    };
  }
};
