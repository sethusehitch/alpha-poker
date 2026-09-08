import { proxyApi } from "../../_proxy";
export function GET(request: Request) { return proxyApi(request, "account/avatar"); }
export async function PUT(request: Request) {
  // Bound reads even when Content-Length is absent (chunked uploads).
  const reader = request.body?.getReader();
  const chunks: Uint8Array[] = [];
  let size = 0;
  if (reader) {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 3 * 1024 * 1024) {
        await reader.cancel();
        return Response.json({ error: { message: "Image is too large. Choose an image under 2 MB." } }, { status: 413 });
      }
      chunks.push(value);
    }
  }
  const body = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
  return proxyApi(new Request(request.url, { method: "PUT", headers: request.headers, body }), "account/avatar");
}
