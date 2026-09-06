"use client";

import { useEffect, useRef, useState } from "react";
import { onToast, type ToastDetail } from "./toastBus";

function CheckGlyph() {
  return (
    <span aria-hidden="true" className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-600 text-white">
      <svg viewBox="0 0 16 16" className="h-3 w-3" fill="none">
        <path d="M3 8.5 6.5 12l6.5-8" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function ErrorGlyph() {
  return (
    <span aria-hidden="true" className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-red-600 text-white text-xs font-bold">
      !
    </span>
  );
}

export function ToastHost() {
  const [toast, setToast] = useState<ToastDetail | null>(null);
  const [visible, setVisible] = useState(false);
  const timerRef = useRef<number | null>(null);
  const remainingRef = useRef(0);
  const startedAtRef = useRef(0);

  function clearTimer() {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }

  function dismiss() {
    clearTimer();
    setVisible(false);
    window.setTimeout(() => setToast(null), 150);
  }

  function startTimer(durationMs: number) {
    clearTimer();
    startedAtRef.current = Date.now();
    remainingRef.current = durationMs;
    timerRef.current = window.setTimeout(dismiss, durationMs);
  }

  function pauseTimer() {
    if (timerRef.current === null) return;
    clearTimer();
    remainingRef.current -= Date.now() - startedAtRef.current;
  }

  function resumeTimer() {
    if (remainingRef.current > 0) startTimer(Math.max(remainingRef.current, 300));
  }

  useEffect(() => {
    return onToast((detail) => {
      setToast(detail);
      setVisible(true);
      startTimer(detail.actionLabel ? 10000 : 4000);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => () => clearTimer(), []);

  if (!toast) return null;

  return (
    <div
      role={toast.kind === "error" ? "alert" : "status"}
      aria-live={toast.kind === "error" ? undefined : "polite"}
      onMouseEnter={pauseTimer}
      onMouseLeave={resumeTimer}
      onFocus={pauseTimer}
      onBlur={resumeTimer}
      onClick={dismiss}
      className={`fixed inset-x-4 bottom-[5.25rem] z-60 flex h-12 cursor-pointer items-center gap-3 rounded-[10px] border border-zinc-200 bg-white px-4 shadow-[0_12px_32px_rgba(9,9,11,0.12)] transition-[opacity,transform] duration-150 ease-out motion-reduce:transition-none sm:inset-x-auto sm:bottom-[5.5rem] sm:right-6 sm:w-auto ${
        visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-1.5"
      }`}
    >
      {toast.kind === "error" ? <ErrorGlyph /> : <CheckGlyph />}
      <p className="text-[0.875rem] font-medium text-zinc-900">{toast.message}</p>
      {toast.actionLabel && toast.onAction && (
        <button
          type="button"
          onClick={(event) => {
            event.stopPropagation();
            toast.onAction?.();
            dismiss();
          }}
          className="ml-1 shrink-0 whitespace-nowrap text-[0.8125rem] font-semibold text-blue-700 hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
        >
          {toast.actionLabel}
        </button>
      )}
    </div>
  );
}
