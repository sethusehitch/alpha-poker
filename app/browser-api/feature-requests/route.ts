import { proxyApi } from "../_proxy";

export async function GET(request: Request) {
  const url = new URL(request.url);
  return proxyApi(request, `feature-requests${url.search}`);
}

export async function POST(request: Request) {
  return proxyApi(request, "feature-requests");
}
