import { proxyApi } from "../../_proxy";

export async function GET(request: Request, { params }: { params: Promise<{ username: string }> }) {
  const { username } = await params;
  return proxyApi(request, `rivals/${encodeURIComponent(username)}`);
}
