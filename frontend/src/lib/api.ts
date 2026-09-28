// Thin fetch wrapper around the FastAPI backend (same origin; cookies carry the JWT).
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Opts = RequestInit & { json?: unknown };

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const { json, ...rest } = opts;
  const init: RequestInit = { credentials: "same-origin", ...rest };
  if (json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "content-type": "application/json", ...(init.headers || {}) };
    init.body = JSON.stringify(json);
  }
  const r = await fetch(path, init);
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new ApiError((data && (data as any).detail) || `Error ${r.status}`, r.status);
  return data as T;
}

export const postForm = <T = any>(path: string, fd: FormData) => api<T>(path, { method: "POST", body: fd });
