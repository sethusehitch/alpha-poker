export type ToastKind = "success" | "error";

export type ToastDetail = {
  message: string;
  kind: ToastKind;
  actionLabel?: string;
  onAction?: () => void;
};

const TOAST_EVENT = "alphapoker:toast";

export function showToast(detail: ToastDetail) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<ToastDetail>(TOAST_EVENT, { detail }));
}

export function onToast(handler: (detail: ToastDetail) => void) {
  if (typeof window === "undefined") return () => undefined;
  const listener = (event: Event) => handler((event as CustomEvent<ToastDetail>).detail);
  window.addEventListener(TOAST_EVENT, listener);
  return () => window.removeEventListener(TOAST_EVENT, listener);
}
