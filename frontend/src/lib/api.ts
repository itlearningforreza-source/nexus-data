import type { User } from './types';

const TOKEN_KEY = 'nexus_token';
const USER_KEY = 'nexus_user';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function setStoredUser(user: User | null) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}

export class ApiError extends Error {
  status: number;
  code?: string;
  errorId?: string;
  details?: Record<string, unknown>;

  constructor(message: string, status: number, code?: string, errorId?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.errorId = errorId;
    this.details = details;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
  form?: FormData;
  timeout?: number;
}

const PUBLIC_PATHS = new Set(['/api/auth/login', '/api/auth/register', '/health']);

export async function api<T = unknown>(path: string, opts: RequestOptions = {}): Promise<T> {
  let url = path;
  if (opts.query) {
    const q = new URLSearchParams();
    for (const [k, v] of Object.entries(opts.query)) {
      if (v !== undefined && v !== null && v !== '') q.set(k, String(v));
    }
    const qs = q.toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }

  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.body !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(opts.body);
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), opts.timeout ?? 180000);

  let res: Response;
  try {
    res = await fetch(url, {
      method: opts.method ?? 'GET',
      headers,
      body,
      signal: controller.signal,
    });
  } catch (err) {
    if (err instanceof Error && err.name === 'AbortError') {
      throw new ApiError('Request timed out.', 408, 'timeout');
    }
    throw new ApiError('Network error. Is the backend running on port 8000?', 0, 'network');
  } finally {
    clearTimeout(timer);
  }

  const contentType = res.headers.get('content-type') || '';
  const text = await res.text();
  let data: unknown = null;
  if (contentType.includes('application/json') && text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text.slice(0, 500) };
    }
  }

  if (!res.ok) {
    const errData = (data ?? {}) as { message?: string; code?: string; error_id?: string; detail?: Record<string, unknown> | Array<{ msg: string }> };
    let message = errData.message;
    if (!message && Array.isArray(errData.detail)) {
      message = errData.detail.map((d) => d.msg).join('; ');
    }
    if (!message) message = 'Request failed.';

    if (!PUBLIC_PATHS.has(path) && res.status === 401) {
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('nexus:unauthorized'));
      }
    }
    throw new ApiError(message, res.status, errData.code, errData.error_id, Array.isArray(errData.detail) ? undefined : errData.detail);
  }

  return data as T;
}

export const q = (key: string | number | null | undefined, dflt = '') => (key === null || key === undefined ? dflt : String(key));