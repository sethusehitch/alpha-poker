import { proxyApi } from "../../../../../_proxy";
export async function GET(request: Request, { params }: { params: Promise<{ runId: string; matchupId: string }> }) {
  const { runId, matchupId } = await params;
  return proxyApi(request, `runs/${encodeURIComponent(runId)}/matchups/${encodeURIComponent(matchupId)}/recap`);
}
