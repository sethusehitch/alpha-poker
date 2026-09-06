// Minimal cross-component event bus. SiteHeader, AuthButton, FeedbackWidget,
// and the feature-request surfaces are independent client components with no
// shared React tree above `layout.tsx`, so coordinating "open the account
// dialog" / "close other panels" style requests needs a channel that does not
// require lifting state into a shared provider.
type UiEvents = {
  "open-account": { openSuggestAfterLogin?: boolean };
  "account-dialog-changed": { open: boolean };
  "suggest-dialog-changed": { open: boolean };
  "rivals-dialog-changed": { open: boolean };
  "session-changed": { username: string | null; isOperator: boolean };
  "close-panels": Record<string, never>;
  "open-feedback-panel": { focusTextarea?: boolean };
};

function eventName<K extends keyof UiEvents>(key: K) {
  return `alphapoker:${key}`;
}

export function emit<K extends keyof UiEvents>(key: K, detail: UiEvents[K]) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(eventName(key), { detail }));
}

export function on<K extends keyof UiEvents>(key: K, handler: (detail: UiEvents[K]) => void) {
  if (typeof window === "undefined") return () => undefined;
  const listener = (event: Event) => handler((event as CustomEvent<UiEvents[K]>).detail);
  window.addEventListener(eventName(key), listener);
  return () => window.removeEventListener(eventName(key), listener);
}
