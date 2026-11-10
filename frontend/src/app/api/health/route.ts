// Liveness check for the frontend container: is the Next.js server answering?
// It deliberately does not call the backend, which has its own /health.

export async function GET() {
  return Response.json({ status: "ok", service: "nexus-frontend" });
}
