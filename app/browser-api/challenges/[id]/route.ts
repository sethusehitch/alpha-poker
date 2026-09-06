import { proxyApi } from "../../_proxy";

export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyApi(request, `challenges/${encodeURIComponent(id)}`);
}
