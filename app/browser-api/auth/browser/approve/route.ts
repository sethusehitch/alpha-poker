import { proxyApi } from "../../../_proxy";
export async function POST(request: Request) {
  if (request.headers.get("origin") !== new URL(request.url).origin) return new Response(null, { status: 403 });
  return proxyApi(request, "auth/browser/approve");
}
