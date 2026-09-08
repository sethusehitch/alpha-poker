import { browserSessionResponse, proxyApi } from "../../../_proxy";

function cookie(request: Request, name: string) {
  return (request.headers.get("cookie") ?? "").split(";").map(s => s.trim()).find(s => s.startsWith(name + "="))?.slice(name.length + 1) ?? "";
}
function setCookie(response: Response, request: Request, name: string, value: string, age = 600) {
  response.headers.append("Set-Cookie", `${name}=${value}; HttpOnly; SameSite=Lax; Path=/; Max-Age=${age}${request.url.startsWith("https:") ? "; Secure" : ""}`);
}
function internal(request: Request, body: unknown) {
  const headers = new Headers(request.headers);
  headers.set("Content-Type", "application/json");
  return new Request(request.url, { method: "POST", headers, body: JSON.stringify(body) });
}
function redirect(request: Request, path: string) {
  return new Response(null, { status: 303, headers: { Location: new URL(path, request.url).href, "Cache-Control": "no-store" } });
}
function sameOrigin(request: Request) {
  return request.headers.get("origin") === new URL(request.url).origin;
}
function safeReturn(value: unknown) {
  if (typeof value !== "string") return "/";
  return /^(?:\/(?:profile|my-bot|leaderboard|rivals|feature-requests|contribute)?)(?:#[A-Za-z0-9_-]+)?$/.test(value) ? value : "/";
}

export async function GET(request: Request, context: { params: Promise<{ action: string }> }) {
  const { action } = await context.params;
  if (action === "connection") return proxyApi(request, "auth/google/connection");
  if (action === "pending") return proxyApi(internal(request, { ticket: cookie(request, "alpha_google_signup") }), "auth/google/pending");
  if (action !== "callback") return new Response(null, { status: 404 });
  const query = new URL(request.url).searchParams;
  const state = cookie(request, "alpha_google_state");
  const failed = () => {
    const response = redirect(request, cookie(request, "alpha_google_next") === "cli" ? "/authorize-cli?login_error=google" : "/?login_error=google");
    setCookie(response, request, "alpha_google_state", "", 0);
    setCookie(response, request, "alpha_google_next", "", 0);
    return response;
  };
  if (!state || query.get("state") !== state || !query.get("code") || query.has("error")) return failed();
  const upstream = await proxyApi(internal(request, { state, code: query.get("code") }), "auth/google/callback");
  if (!upstream.ok) return failed();
  const result = await upstream.json();
  const cli = cookie(request, "alpha_google_next") === "cli";
  let response: Response;
  if (result.signup_required && typeof result.ticket === "string") {
    response = redirect(request, cli ? "/join?next=cli" : "/join");
    setCookie(response, request, "alpha_google_signup", result.ticket);
  } else if (result.linked) {
    response = redirect(request, "/profile?google=connected");
  } else {
    const session = await browserSessionResponse(Response.json(result), request.url);
    if (!session.ok) return failed();
    let returnTo = "/";
    try { returnTo = safeReturn(decodeURIComponent(cookie(request, "alpha_google_return"))); } catch { /* malformed cookie falls back home */ }
    response = redirect(request, cli ? "/authorize-cli" : returnTo);
    response.headers.append("Set-Cookie", session.headers.get("Set-Cookie")!);
  }
  setCookie(response, request, "alpha_google_state", "", 0);
  setCookie(response, request, "alpha_google_next", "", 0);
  setCookie(response, request, "alpha_google_return", "", 0);
  return response;
}

export async function POST(request: Request, context: { params: Promise<{ action: string }> }) {
  if (!sameOrigin(request)) return Response.json({ error: { message: "Refresh this page and try again." } }, { status: 403 });
  const { action } = await context.params;
  if (!["start", "invite", "complete"].includes(action)) return new Response(null, { status: 404 });
  let body;
  try { body = await request.json(); } catch { return new Response(null, { status: 400 }); }
  if (action === "start") {
    const upstream = await proxyApi(internal(request, { link: body.link === true }), "auth/google/start");
    if (!upstream.ok) return upstream;
    const result = await upstream.json();
    const callback = new URL(new URL(result.url).searchParams.get("redirect_uri")!);
    if (callback.origin !== new URL(request.url).origin) {
      return Response.json({ error: { code: "google_origin", message: "Google sign-in is available on the main Alpha Poker address.", url: callback.origin } }, { status: 409 });
    }
    const response = Response.json({ url: result.url }, { headers: { "Cache-Control": "no-store" } });
    setCookie(response, request, "alpha_google_state", result.state);
    setCookie(response, request, "alpha_google_next", body.next === "cli" ? "cli" : "site");
    setCookie(response, request, "alpha_google_return", encodeURIComponent(safeReturn(body.returnTo)));
    setCookie(response, request, "alpha_google_signup", "", 0);
    return response;
  }
  const upstream = await proxyApi(internal(request, { ...body, ticket: cookie(request, "alpha_google_signup") }), `auth/google/${action}`);
  if (action !== "complete" || !upstream.ok) return upstream;
  const response = await browserSessionResponse(upstream, request.url);
  setCookie(response, request, "alpha_google_signup", "", 0);
  return response;
}
