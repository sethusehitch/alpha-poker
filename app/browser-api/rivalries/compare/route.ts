import { proxyApi } from "../../_proxy";

export async function GET(request: Request) { return proxyApi(request, `rivalries/compare${new URL(request.url).search}`); }
