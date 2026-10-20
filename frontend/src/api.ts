let csrf = '';
export function setCsrf(value: string) { csrf = value; }
export class ApiError extends Error { constructor(message: string, public status: number) { super(message); } }
export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const base = import.meta.env.VITE_API_URL || '';
  const response = await fetch(`${base}/api${path}`, {
    method, credentials: 'include',
    headers: { ...(body !== undefined ? { 'Content-Type': 'application/json' } : {}), ...(method !== 'GET' ? { 'X-CSRF-Token': csrf } : {}) },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    const message = typeof result.detail === 'string' ? result.detail : Array.isArray(result.detail) ? result.detail.map((e: { msg: string }) => e.msg).join('. ') : 'Unable to complete this request. Please try again.';
    if (response.status === 401 && path !== '/auth/login') window.dispatchEvent(new Event('session-expired'));
    throw new ApiError(message, response.status);
  }
  return response.status === 204 ? undefined as T : response.json();
}
