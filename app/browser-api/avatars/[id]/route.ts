import { proxyApi } from "../../_proxy";
export async function GET(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[a-f0-9]{64}$/.test(id)) return new Response(null, { status: 404 });
  const response = await proxyApi(request, `avatars/${id}`);
  response.headers.set("X-Content-Type-Options", "nosniff");
  return response;
}
