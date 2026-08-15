// Empty means same-origin: the app and the API are served from one domain
// through the gateway, so requests use a relative "/api/..." path. Set
// NEXT_PUBLIC_API_URL only when the API lives on a different origin (e.g. running
// the frontend on its own during local development).
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const isForm = options.body instanceof FormData;
  const response = await fetch(`${API_URL}/api${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...options.headers,
    },
  });
  if (!response.ok) {
    let message = "An unexpected error occurred";
    try {
      const data = await response.json();
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail) && typeof data.detail[0]?.msg === "string") {
        message = `Revisa los campos del formulario: ${data.detail[0].msg}`;
      }
    } catch {}
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "An unexpected error occurred";
}
