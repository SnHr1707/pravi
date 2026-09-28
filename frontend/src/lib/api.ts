// Thin fetch wrapper around the FastAPI backend (same origin; cookies carry the JWT).
export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type Opts = RequestInit & { json?: unknown };

// The office (circle / division / sub-division) a senior officer is currently looking at.
export function getViewOffice(): string | null {
  try { return localStorage.getItem("pravi_office"); } catch { return null; }
}
export function setViewOffice(id: number | null) {
  try { if (id === null) localStorage.removeItem("pravi_office"); else localStorage.setItem("pravi_office", String(id)); } catch { /* ignore */ }
}

export async function api<T = any>(path: string, opts: Opts = {}): Promise<T> {
  const { json, ...rest } = opts;
  const init: RequestInit = { credentials: "same-origin", ...rest };
  const office = getViewOffice();
  if (office) init.headers = { "x-pravi-office": office, ...((init.headers as Record<string, string>) || {}) };
  if (json !== undefined) {
    init.method = init.method || "POST";
    init.headers = { "content-type": "application/json", ...((init.headers as Record<string, string>) || {}) };
    init.body = JSON.stringify(json);
  }
  const r = await fetch(path, init);
  const ct = r.headers.get("content-type") || "";
  const data = ct.includes("json") ? await r.json() : await r.text();
  if (!r.ok) throw new ApiError((data && (data as any).detail) || `Error ${r.status}`, r.status);
  return data as T;
}

export const postForm = <T = any>(path: string, fd: FormData) => api<T>(path, { method: "POST", body: fd });
