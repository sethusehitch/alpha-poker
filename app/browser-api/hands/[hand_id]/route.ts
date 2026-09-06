import { proxyApi } from "../../_proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ hand_id: string }> },
) {
  const { hand_id } = await params;
  return proxyApi(request, `hands/${encodeURIComponent(hand_id)}`);
}
