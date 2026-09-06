import { proxyApi } from "../_proxy";

// The dedicated /leaderboard page needs the signed-in caller's identity so the
// API can answer with `viewer_entry` when their rank falls outside the top 5.
export async function GET(request: Request) {
  return proxyApi(request, "leaderboard");
}
