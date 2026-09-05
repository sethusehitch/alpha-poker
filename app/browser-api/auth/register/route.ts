import { browserSessionResponse, proxyApi } from "../../_proxy";

export async function POST(request: Request) {
  return browserSessionResponse(await proxyApi(request, "auth/register"), request.url);
}
