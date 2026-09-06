import { proxyApi } from "../../../_proxy";

export async function POST(request: Request, context: { params: Promise<{ id: string }> }) {
  const { id } = await context.params;
  return proxyApi(request, `feature-requests/${encodeURIComponent(id)}/vote`);
}
