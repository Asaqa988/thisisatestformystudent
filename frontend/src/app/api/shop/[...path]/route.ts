// The public shop page's only door to the backend.
//
//   browser  ->  /api/shop/shop                      ->  GET  /api/v1/public/shop
//   browser  ->  /api/shop/products/<id>/image?v=..  ->  GET  /api/v1/public/products/<id>/image
//   browser  ->  /api/shop/voice-ticket              ->  POST /api/v1/public/voice-ticket
//
// Unlike /api/nexus, this route needs no login (see proxy.ts) and can reach only
// the backend's public endpoints: the prefix is fixed here and every segment is
// encoded, so a path cannot climb out of /api/v1/public.

import type { NextRequest } from "next/server";

const DEFAULT_BACKEND = "http://localhost:8100";
const ALLOWED = [
  { method: "GET", pattern: /^shop$/ },
  { method: "GET", pattern: /^products\/[0-9a-f-]{36}\/image$/ },
  { method: "POST", pattern: /^voice-ticket$/ },
];

function backendUrl() {
  return (process.env.NEXUS_API_URL ?? DEFAULT_BACKEND).replace(/\/+$/, "");
}

function errorResponse(status: number, code: string, message: string) {
  return Response.json({ error: { code, message } }, { status });
}

async function forward(request: NextRequest, ctx: RouteContext<"/api/shop/[...path]">) {
  const { path } = await ctx.params;
  const joined = path.join("/");
  if (!ALLOWED.some((rule) => rule.method === request.method && rule.pattern.test(joined))) {
    return errorResponse(404, "not_found", "Unknown shop endpoint.");
  }

  const query = joined.endsWith("/image") ? request.nextUrl.search : "";
  const target = `${backendUrl()}/api/v1/public/${path.map(encodeURIComponent).join("/")}${query}`;

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers: {
        Accept: "application/json, image/*",
        ...(process.env.NEXUS_API_KEY ? { "X-NEXUS-API-Key": process.env.NEXUS_API_KEY } : {}),
      },
      cache: "no-store",
      signal: AbortSignal.timeout(15_000),
    });
    const contentType = upstream.headers.get("content-type") ?? "application/json";
    const isImage = contentType.startsWith("image/");
    return new Response(isImage ? await upstream.arrayBuffer() : await upstream.text(), {
      status: upstream.status,
      headers: {
        "Content-Type": contentType,
        // Image URLs change when the image changes (?v=...), so they may be cached.
        "Cache-Control":
          isImage && upstream.ok ? "public, max-age=86400, immutable" : "no-store",
      },
    });
  } catch {
    return errorResponse(502, "backend_unavailable", "The shop is not responding. Try again soon.");
  }
}

export { forward as GET, forward as POST };
