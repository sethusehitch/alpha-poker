import { proxyApi } from "../../../_proxy";

export async function GET(request: Request, context: { params: Promise<{ submissionId: string }> }) {
  const { submissionId } = await context.params;
  return proxyApi(request, `submissions/${encodeURIComponent(submissionId)}/logs`);
}
