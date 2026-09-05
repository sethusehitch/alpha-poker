import { proxyApi } from "../../../_proxy";

export async function GET(request: Request, context: { params: Promise<{ runId: string }> }) {
  const { runId } = await context.params;
  return proxyApi(request, `runs/${encodeURIComponent(runId)}/artifacts`);
}
