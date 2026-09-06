import { proxyApi } from "../_proxy";

export async function GET(request: Request) { return proxyApi(request, `challenges${new URL(request.url).search}`); }
export async function POST(request: Request) { return proxyApi(request, "challenges"); }
