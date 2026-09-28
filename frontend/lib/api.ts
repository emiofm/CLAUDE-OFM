export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function messageFrom(body: unknown, fallback: string): string {
  if (body && typeof body === "object") {
    const b = body as Record<string, unknown>;
    if (typeof b.message === "string") return b.message;
    if (typeof b.detail === "string") return b.detail;
    if (Array.isArray(b.detail)) {
      return b.detail
        .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`)
        .join("; ");
    }
    if (b.detail && typeof b.detail === "object" && typeof (b.detail as Record<string, unknown>).message === "string")
      return (b.detail as Record<string, string>).message;
  }
  return fallback;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, credentials: "include", cache: "no-store" });
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL}. Is it running?`, null);
  }
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    body = text;
  }
  if (!res.ok) throw new ApiError(res.status, messageFrom(body, `Request failed (${res.status})`), body);
  return body as T;
}

export const jsonInit = (method: string, data: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(data),
});

export const assetUrl = (path: string) => (path.startsWith("http") ? path : `${API_URL}${path}`);
