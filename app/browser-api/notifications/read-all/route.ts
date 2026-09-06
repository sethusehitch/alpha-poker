import { proxyApi } from "../../_proxy";
export async function POST(request: Request) { return proxyApi(request, "notifications/read-all"); }
