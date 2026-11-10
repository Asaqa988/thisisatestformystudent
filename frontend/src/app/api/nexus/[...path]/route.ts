// The browser's only door to the NEXUS backend.
//
//   browser  ->  /api/nexus/api/v1/conversations  ->  FastAPI /api/v1/conversations
//
// Why a route and not a rewrite in next.config.ts: rewrites are fixed when the
// app is built, while this reads NEXUS_API_URL on every request. The same image
// therefore works in Docker (http://backend:8000) and on a laptop.

import type { NextRequest } from "next/server";

const DEFAULT_BACKEND = "http://localhost:8100";

function backendUrl() {
  return (process.env.NEXUS_API_URL ?? DEFAULT_BACKEND).replace(/\/+$/, "");
}

/** Only application endpoints are reachable. Webhooks are for Chatwoot, not browsers. */
function isAllowed(segments: string[]) {
  if (segments.some((s) => s === "." || s === ".." || s === "")) return false;
  const path = segments.join("/");
  if (path.startsWith("api/v1/webhooks")) return false;
  return path === "health" || path.startsWith("health/") || path.startsWith("api/v1/");
}

function errorResponse(status: number, code: string, message: string) {
  return Response.json({ error: { code, message } }, { status });
}

async function forward(request: NextRequest, ctx: RouteContext<"/api/nexus/[...path]">) {
  const { path } = await ctx.params;

  if (!isAllowed(path)) {
    return errorResponse(404, "not_found", "Unknown NEXUS endpoint.");
  }

  const target = `${backendUrl()}/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const hasBody = request.method !== "GET" && request.method !== "HEAD";

  try {
    const upstream = await fetch(target, {
      method: request.method,
      // Forward only what the backend needs. Cookies and other headers stay here.
      headers: {
        Accept: "application/json",
        ...(hasBody ? { "Content-Type": "application/json" } : {}),
        // Proves to a deployed backend that the call comes from this server.
        // Read from the server environment; never sent to the browser.
        ...(process.env.NEXUS_API_KEY ? { "X-NEXUS-API-Key": process.env.NEXUS_API_KEY } : {}),
      },
      body: hasBody ? await request.text() : undefined,
      cache: "no-store",
      signal: AbortSignal.timeout(20_000),
    });

    return new Response(await upstream.text(), {
      status: upstream.status,
      headers: {
        "Content-Type": upstream.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
      },
    });
  } catch {
    return errorResponse(
      502,
      "backend_unavailable",
      "The NEXUS backend is not responding. Is the backend container running?",
    );
  }
}

export { forward as GET, forward as POST };
