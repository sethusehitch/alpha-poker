const baseUrl = process.argv[2] ?? "http://localhost:8080";
const username = process.env.ALPHA_POKER_SMOKE_USERNAME ?? "container-smoke";
const password = process.env.ALPHA_POKER_SMOKE_PASSWORD ?? "alpha-poker-local-smoke-only";
let authenticated = await fetch(`${baseUrl}/v1/auth/register`, {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({
    username,
    password,
    ...(process.env.ALPHA_POKER_INVITE_CODE
      ? { invite_code: process.env.ALPHA_POKER_INVITE_CODE }
      : {}),
  }),
});

if (authenticated.status === 409) {
  authenticated = await fetch(`${baseUrl}/v1/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

if (!authenticated.ok) {
  throw new Error(`Could not authenticate smoke account: HTTP ${authenticated.status}`);
}

const account = await authenticated.json();

const participantStatus = await fetch(`${baseUrl}/v1/account/status`, {
  headers: { authorization: `Bearer ${account.token}` },
});
if (!participantStatus.ok) {
  throw new Error(`Could not read participant status: HTTP ${participantStatus.status}`);
}
const participant = await participantStatus.json();
if (typeof participant.participant_state !== "string" || typeof participant.participant_message !== "string") {
  throw new Error("Participant status is missing its state or message");
}

const created = await fetch(`${baseUrl}/v1/training/sessions`, {
  method: "POST",
  headers: {
    "content-type": "application/json",
    authorization: `Bearer ${account.token}`,
  },
  body: JSON.stringify({ username, hand_limit: 1 }),
});

if (!created.ok) {
  throw new Error(`Could not create training session: HTTP ${created.status}`);
}

const session = await created.json();
const websocketUrl = new URL(session.websocket_url, baseUrl);
websocketUrl.protocol =
  new URL(baseUrl).protocol === "https:" || websocketUrl.protocol === "https:" || websocketUrl.protocol === "wss:"
    ? "wss:"
    : "ws:";
const safeWebsocketTarget = `${websocketUrl.origin}${websocketUrl.pathname}`;

await new Promise((resolve, reject) => {
  const websocket = new WebSocket(websocketUrl);
  const timeout = setTimeout(() => {
    websocket.close();
    reject(new Error("Timed out waiting for a training WebSocket event"));
  }, 10_000);

  websocket.addEventListener("message", (event) => {
    const message = JSON.parse(String(event.data));
    if (message.type === "action.requested") {
      clearTimeout(timeout);
      websocket.close();
      resolve();
    }
  });
  websocket.addEventListener("error", () => {
    // The close event carries the useful status code and sanitized reason.
  });
  websocket.addEventListener("close", (event) => {
    clearTimeout(timeout);
    if (event.code !== 1000) {
      reject(
        new Error(
          `Training WebSocket ${safeWebsocketTarget} closed before an action request: code=${event.code} reason=${event.reason || "none"}`,
        ),
      );
    }
  });
});

console.log("Training WebSocket smoke test passed");
