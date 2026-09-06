export const LOCAL_API = process.env.ALPHA_POKER_API_URL ?? "http://127.0.0.1:8000/v1";

/** Used by server components that only have a raw `cookie` header, not a Request. */
export function authorizationFromCookieHeader(cookieHeader: string | null): string | null {
  const match = (cookieHeader ?? "").match(/(?:^|;\s*)alpha_poker_session=([^;]+)/);
  return match ? `Bearer ${decodeURIComponent(match[1])}` : null;
}

/** Best-effort server-side fetch for prerendering public data; callers must handle failure. */
export async function serverFetchJson(path: string, authorization: string | null, timeoutMs = 2500) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const headers = new Headers({ Accept: "application/json" });
    if (authorization) headers.set("Authorization", authorization);
    const response = await fetch(`${LOCAL_API.replace(/\/$/, "")}/${path.replace(/^\//, "")}`, {
      headers,
      signal: controller.signal,
      cache: "no-store",
    });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  } finally {
    clearTimeout(timeout);
  }
}

export async function proxyApi(request: Request, path: string) {
  try {
    const headers = new Headers({ Accept: "application/json" });
    const contentType = request.headers.get("content-type");
    const authorization = request.headers.get("authorization") ?? browserAuthorization(request);
    const forwardedFor = request.headers.get("x-forwarded-for");
    const userAgent = request.headers.get("user-agent");
    if (contentType) headers.set("Content-Type", contentType);
    if (authorization) headers.set("Authorization", authorization);
    // Preserve the client address Caddy supplied to the web container so the
    // API's account limiter cannot be exhausted globally through this proxy.
    if (forwardedFor) headers.set("X-Forwarded-For", forwardedFor.split(",", 1)[0].trim());
    if (userAgent) headers.set("User-Agent", userAgent.slice(0, 300));
    const body = request.method === "GET" || request.method === "HEAD" ? undefined : await request.text();
    const response = await fetch(
      `${LOCAL_API.replace(/\/$/, "")}/${path.replace(/^\//, "")}`,
      { method: request.method, headers, body, cache: "no-store" },
    );
    const responseHeaders = new Headers({
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "no-store",
    });
    const disposition = response.headers.get("content-disposition");
    if (disposition) responseHeaders.set("Content-Disposition", disposition);
    return new Response(response.status === 204 ? null : await response.arrayBuffer(), {
      status: response.status,
      headers: responseHeaders,
    });
  } catch {
    return Response.json(
      { error: { code: "api_unavailable", message: "The local Alpha Poker API is unavailable" } },
      { status: 503 },
    );
  }
}

function browserAuthorization(request: Request) {
  const cookie = request.headers.get("cookie") ?? "";
  const match = cookie.match(/(?:^|;\s*)alpha_poker_session=([^;]+)/);
  return match ? `Bearer ${decodeURIComponent(match[1])}` : null;
}

export async function browserSessionResponse(response: Response, requestUrl: string) {
  if (!response.ok) return response;
  const result = await response.json();
  if (typeof result.token !== "string" || typeof result.username !== "string") {
    return Response.json(
      { error: { code: "session_invalid", message: "The API returned an invalid session" } },
      { status: 502 },
    );
  }
  return Response.json(
    { username: result.username, expires_at: result.expires_at },
    {
      status: response.status,
      headers: {
        "Cache-Control": "no-store",
        "Set-Cookie": `alpha_poker_session=${encodeURIComponent(result.token)}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000${requestUrl.startsWith("https:") ? "; Secure" : ""}`,
      },
    },
  );
}

export function clearBrowserSession(response: Response) {
  const headers = new Headers(response.headers);
  headers.set("Set-Cookie", "alpha_poker_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0");
  return new Response(response.body, { status: response.status, headers });
}
