// One small client for the NEXUS backend.
//
// The browser calls /api/nexus/... on this same origin. A server route
// (src/app/api/nexus/[...path]/route.ts) forwards the call to FastAPI, so the
// backend address and every credential stay on the server.

const BASE = "/api/nexus";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** True when Chatwoot credentials have not been added to .env yet. */
  get notConfigured() {
    return this.code === "integration_not_configured";
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(0, "network_error", "Could not reach NEXUS. Check your connection.");
  }

  const body = response.status === 204 ? null : await response.json().catch(() => null);

  if (!response.ok) {
    const error = body?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "unknown_error",
      error?.message ?? `Request failed with status ${response.status}.`,
    );
  }

  return body as T;
}

/** The fetcher SWR uses for every GET. */
export const fetcher = <T,>(path: string) => api<T>(path);
