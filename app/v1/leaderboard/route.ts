const LOCAL_API = process.env.ALPHA_POKER_API_URL ?? "http://127.0.0.1:8000/v1";

export async function GET() {
  try {
    const response = await fetch(`${LOCAL_API.replace(/\/$/, "")}/leaderboard`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!response.ok) {
      return Response.json(
        { error: "Leaderboard API is unavailable" },
        { status: response.status },
      );
    }
    return Response.json(await response.json(), {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return Response.json(
      { error: "Leaderboard API is unavailable" },
      { status: 503 },
    );
  }
}
