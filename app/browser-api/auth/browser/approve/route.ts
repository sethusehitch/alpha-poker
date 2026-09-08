import { proxyApi } from "../../../_proxy";
import { samePublicOrigin } from "../../../publicOrigin.mjs";
export async function POST(request: Request) {
  if (!samePublicOrigin(request)) return new Response(null, { status: 403 });
  return proxyApi(request, "auth/browser/approve");
}
