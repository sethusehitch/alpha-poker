import { clearBrowserSession, proxyApi } from "../../_proxy";

export async function POST(request: Request) {
  return clearBrowserSession(await proxyApi(request, "auth/logout"));
}
