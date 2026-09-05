const LOCAL_API = process.env.ALPHA_POKER_API_URL ?? "http://127.0.0.1:8000/v1";

export async function proxyApi(request: Request, path: string) {
  try {
    const headers = new Headers({ Accept: "application/json" });
    const contentType = request.headers.get("content-type");
    const authorization = request.headers.get("authorization") ?? browserAuthorization(request);
    if (contentType) headers.set("Content-Type", contentType);
    if (authorization) headers.set("Authorization", authorization);
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
