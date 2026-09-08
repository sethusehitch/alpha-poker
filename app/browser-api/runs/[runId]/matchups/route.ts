import { proxyApi } from "../../../_proxy";
export async function GET(request: Request, { params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return proxyApi(request, `runs/${encodeURIComponent(runId)}/matchups`);
}
