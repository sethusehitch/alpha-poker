"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { emit } from "./uiBus";

const TITLE_MAX_LENGTH = 80;
const DETAILS_MAX_LENGTH = 500;
const TITLE_MIN_LENGTH = 4;

type SubmitResult = { title: string; details: string };

const ERROR_COPY: Record<string, string> = {
  validation_error: "That title didn't work. Keep it under 80 characters and try again.",
  duplicate_request: "Someone already suggested that. Look for it in the list.",
  rate_limited: "You're posting quickly. Try again in a minute.",
  api_unavailable: "Couldn't post that. Check your connection and try again.",
};

function errorCopyFor(code: string | undefined, status: number): string {
  if (code && ERROR_COPY[code]) return ERROR_COPY[code];
  if (status === 503 || status === 0) return ERROR_COPY.api_unavailable;
  return "Something went wrong on our side. Try again.";
}

export function SuggestFeatureDialog({
  open,
  onClose,
  onPosted,
  isSignedIn,
}: {
  open: boolean;
  onClose: () => void;
  onPosted: (result: SubmitResult & { id: string }) => void;
  isSignedIn: boolean;
}) {
  const [title, setTitle] = useState("");
  const [details, setDetails] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [invalidTitle, setInvalidTitle] = useState(false);
  const titleRef = useRef<HTMLInputElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => emit("suggest-dialog-changed", { open }), [open]);

  useEffect(() => {
    if (!open) return;
    triggerFocusRef.current = document.activeElement as HTMLElement;
    titleRef.current?.focus();
    document.documentElement.classList.add("overflow-hidden");
    return () => {
      document.documentElement.classList.remove("overflow-hidden");
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !submitting) {
        event.preventDefault();
        onClose();
        triggerFocusRef.current?.focus();
        return;
      }
      if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
        event.preventDefault();
        void submit();
      }
      if (event.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), textarea:not([disabled])',
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, submitting, title, details]);

  if (!open) return null;

  async function submit() {
    if (submitting) return;
    const trimmedTitle = title.trim();
    if (Array.from(trimmedTitle).length < TITLE_MIN_LENGTH) {
      setInvalidTitle(true);
      return;
    }
    setInvalidTitle(false);
    setError("");
    setSubmitting(true);
    try {
      const response = await fetch("/browser-api/feature-requests", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmedTitle, details: details.trim() || null }),
      });
      const result = await response.json().catch(() => ({}));
      if (!response.ok) {
        if (response.status === 401) {
          onClose();
          emit("open-account", {});
          return;
        }
        setError(errorCopyFor(result?.error?.code, response.status));
        return;
      }
      onPosted({ id: result.id, title: result.title, details: result.details ?? "" });
      setTitle("");
      setDetails("");
    } catch {
      setError(ERROR_COPY.api_unavailable);
    } finally {
      setSubmitting(false);
    }
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    void submit();
  }

  function handleOverlayMouseDown() {
    if (submitting) return;
    if (title.trim() === "" && details.trim() === "") {
      onClose();
      triggerFocusRef.current?.focus();
    }
  }

  const titleLength = Array.from(title).length;
  const detailsLength = Array.from(details).length;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/20 px-5 max-sm:items-end"
      onMouseDown={handleOverlayMouseDown}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="suggest-title"
        onMouseDown={(event) => event.stopPropagation()}
        className="w-full max-w-[32rem] rounded-2xl border border-zinc-200 bg-white p-6 shadow-[0_20px_48px_rgba(9,9,11,0.18)] max-sm:max-h-[90svh] max-sm:overflow-y-auto max-sm:rounded-b-none max-sm:p-5 max-sm:pb-[max(1.25rem,env(safe-area-inset-bottom))]"
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 id="suggest-title" className="text-xl font-bold text-zinc-900">Suggest a feature</h2>
            <p className="mt-1 text-sm text-zinc-500">Tell us what would make Alpha Poker better.</p>
          </div>
          <button
            type="button"
            aria-label="Close"
            disabled={submitting}
            onClick={() => {
              onClose();
              triggerFocusRef.current?.focus();
            }}
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-[5px] text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60"
          >
            <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none">
              <path d="M3.5 3.5l9 9m0-9-9 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {!isSignedIn && (
          <p className="mt-4 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2.5 text-[0.8125rem] text-blue-700">
            Log in to post this idea under your account.
          </p>
        )}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label htmlFor="suggest-title-input" className="block text-sm font-medium text-zinc-800">
              Title
            </label>
            <input
              id="suggest-title-input"
              ref={titleRef}
              maxLength={TITLE_MAX_LENGTH}
              value={title}
              disabled={submitting}
              placeholder="Watch a hand replay"
              aria-invalid={invalidTitle}
              aria-describedby={invalidTitle ? "suggest-title-error" : undefined}
              onChange={(event) => {
                setTitle(event.target.value);
                if (invalidTitle) setInvalidTitle(false);
              }}
              className="mt-1.5 h-11 w-full rounded-lg border border-zinc-300 px-3 text-[0.9375rem] outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:opacity-60"
            />
            {titleLength > 0 && (
              <p
                className={`mt-1 text-right text-xs ${
                  titleLength >= TITLE_MAX_LENGTH ? "text-red-600" : titleLength >= TITLE_MAX_LENGTH * 0.8 ? "text-zinc-600" : "text-zinc-400"
                }`}
              >
                {titleLength}/{TITLE_MAX_LENGTH}
              </p>
            )}
            {invalidTitle && (
              <p id="suggest-title-error" role="alert" className="mt-1.5 text-[0.8125rem] text-red-600">
                Give your idea a short title (at least 4 characters).
              </p>
            )}
          </div>

          <div>
            <label htmlFor="suggest-details-input" className="block text-sm font-medium text-zinc-800">
              Details (optional)
            </label>
            <textarea
              id="suggest-details-input"
              rows={4}
              maxLength={DETAILS_MAX_LENGTH}
              value={details}
              disabled={submitting}
              placeholder="What would it do? Why would it help?"
              onChange={(event) => setDetails(event.target.value)}
              className="mt-1.5 min-h-[6.5rem] w-full resize-y rounded-lg border border-zinc-300 px-3 py-2.5 text-[0.9375rem] leading-6 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:opacity-60"
            />
            {detailsLength > 0 && (
              <p
                className={`mt-1 text-right text-xs ${
                  detailsLength >= DETAILS_MAX_LENGTH ? "text-red-600" : detailsLength >= DETAILS_MAX_LENGTH * 0.8 ? "text-zinc-600" : "text-zinc-400"
                }`}
              >
                {detailsLength}/{DETAILS_MAX_LENGTH}
              </p>
            )}
          </div>

          {error && (
            <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-[0.8125rem] text-red-700">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3 max-sm:flex-col-reverse">
            <button
              type="button"
              disabled={submitting}
              onClick={() => {
                onClose();
                triggerFocusRef.current?.focus();
              }}
              className="inline-flex h-11 items-center justify-center rounded-[5px] border border-zinc-200 bg-white px-4 text-sm font-semibold text-zinc-700 transition-colors hover:bg-zinc-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60 max-sm:w-full"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || titleLength < TITLE_MIN_LENGTH}
              aria-busy={submitting}
              className="inline-flex h-11 items-center justify-center gap-2 rounded-[5px] bg-blue-600 px-5 text-sm font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60 max-sm:w-full"
            >
              {submitting && (
                <span
                  aria-hidden="true"
                  className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white motion-reduce:animate-none"
                />
              )}
              {submitting ? "Posting…" : "Post idea"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
