// Login for a deployed NEXUS.
//
// Lesson 01 has no user accounts yet. When NEXUS is put on the internet, this
// file asks for one shared username and password (HTTP Basic authentication)
// before any page or API route is served.
//
//   NEXUS_BASIC_AUTH_USER       set both on the hosting platform (e.g. Vercel)
//   NEXUS_BASIC_AUTH_PASSWORD   leave both empty for local development
//
// Runs before every request (Next.js 16 calls this file "proxy", formerly "middleware").

import { type NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  const user = process.env.NEXUS_BASIC_AUTH_USER ?? "";
  const password = process.env.NEXUS_BASIC_AUTH_PASSWORD ?? "";

  // Not configured: local development, no login.
  if (!user || !password) return NextResponse.next();

  const header = request.headers.get("authorization") ?? "";
  if (header.startsWith("Basic ")) {
    const decoded = decodeBase64(header.slice(6));
    const separator = decoded.indexOf(":");
    if (separator >= 0) {
      const givenUser = decoded.slice(0, separator);
      const givenPassword = decoded.slice(separator + 1);
      // Evaluate both comparisons so a wrong username takes as long as a wrong password.
      const userOk = safeEqual(givenUser, user);
      const passwordOk = safeEqual(givenPassword, password);
      if (userOk && passwordOk) return NextResponse.next();
    }
  }

  return new NextResponse("Sign in to NEXUS to continue.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="NEXUS", charset="UTF-8"' },
  });
}

export const config = {
  // Everything except the container health check and Next.js static files.
  matcher: ["/((?!api/health$|_next/static|_next/image|favicon.ico|robots.txt).*)"],
};

function decodeBase64(value: string): string {
  try {
    return new TextDecoder().decode(Uint8Array.from(atob(value), (c) => c.charCodeAt(0)));
  } catch {
    return "";
  }
}

/** Compare without stopping at the first different character. */
function safeEqual(a: string, b: string): boolean {
  const left = new TextEncoder().encode(a);
  const right = new TextEncoder().encode(b);
  let difference = left.length ^ right.length;
  for (let i = 0; i < Math.max(left.length, right.length); i++) {
    difference |= (left[i] ?? 0) ^ (right[i] ?? 0);
  }
  return difference === 0;
}
