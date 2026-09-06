"use client";

import { useEffect, useRef, useState } from "react";
import { emit, on } from "./uiBus";
import { showToast } from "./toastBus";
import { useSession } from "./useSession";

type FeedbackType = "bug" | "idea" | "other";

const TYPES: { key: FeedbackType; label: string; placeholder: string }[] = [
  { key: "bug", label: "Bug", placeholder: "What went wrong? What were you doing?" },
  { key: "idea", label: "Idea", placeholder: "What would make Alpha Poker more fun?" },
  { key: "other", label: "Other", placeholder: "Tell us anything." },
];

const MESSAGE_MAX_LENGTH = 500;
const MESSAGE_MIN_LENGTH = 3;

// Every page transition in this app is a full document load (vinext's worker
// routing has no client-side router), so component state alone loses a draft
// the moment someone clicks a nav link. sessionStorage — scoped to this tab,
// cleared when the tab closes — keeps the draft without the shared-machine
// exposure of localStorage.
const DRAFT_STORAGE_KEY = "alpha-poker:feedback-draft";

const ERROR_COPY: Record<string, string> = {
  api_unavailable: "Couldn't send that. Check your connection and try again.",
  rate_limited: "You're sending a lot right now. Try again in a minute.",
  validation_error: "That message is too long. Keep it under 500 characters.",
};

function isFeedbackType(value: unknown): value is FeedbackType {
  return TYPES.some((option) => option.key === value);
}

function readDraft(): { type: FeedbackType; message: string } | null {
  try {
    const raw = window.sessionStorage.getItem(DRAFT_STORAGE_KEY);
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (typeof parsed !== "object" || parsed === null) return null;
    const { type, message } = parsed as { type?: unknown; message?: unknown };
    if (typeof message !== "string") return null;
    return {
      type: isFeedbackType(type) ? type : "idea",
      message: message.slice(0, MESSAGE_MAX_LENGTH),
    };
  } catch {
    return null;
  }
}

function writeDraft(draft: { type: FeedbackType; message: string } | null) {
  try {
    if (draft === null || draft.message === "") {
      window.sessionStorage.removeItem(DRAFT_STORAGE_KEY);
      return;
    }
    window.sessionStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // Private-mode or quota failures must never break the widget.
  }
}

function SpeechBubbleIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-[22px] w-[22px]" fill="none">
      <path
        d="M4 6.5A2.5 2.5 0 0 1 6.5 4h11A2.5 2.5 0 0 1 20 6.5v7A2.5 2.5 0 0 1 17.5 16H10l-4.5 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-7Z"
        stroke="currentColor"
        strokeWidth="1.75"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" className="h-[22px] w-[22px]" fill="none">
      <path d="M6.5 6.5l11 11m0-11-11 11" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" />
    </svg>
  );
}

export function FeedbackWidget() {
  const { session } = useSession();
  const [open, setOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [rivalsDialogOpen, setRivalsDialogOpen] = useState(false);
  const [type, setType] = useState<FeedbackType>("idea");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [submitLocked, setSubmitLocked] = useState(false);
  const fabRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const typeRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const restoredRef = useRef(false);

  useEffect(() => {
    // Skipped until the panel has been opened once and the stored draft has
    // been restored, so the empty initial state never overwrites it.
    if (!restoredRef.current) return;
    writeDraft(message === "" ? null : { type, message });
  }, [type, message]);

  useEffect(() => on("account-dialog-changed", ({ open }) => setAccountOpen(open)), []);
  useEffect(() => on("suggest-dialog-changed", ({ open }) => setSuggestOpen(open)), []);
  useEffect(
    () =>
      on("rivals-dialog-changed", ({ open }) => {
        setRivalsDialogOpen(open);
        if (open) setOpen(false);
      }),
    [],
  );

  useEffect(() => {
    return on("close-panels", () => setOpen(false));
  }, []);

  useEffect(() => {
    return on("open-feedback-panel", () => {
      openPanel();
      window.setTimeout(() => textareaRef.current?.focus(), 0);
    });
  }, []);

  useEffect(() => {
    if (open) textareaRef.current?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && !sending) {
        setOpen(false);
        fabRef.current?.focus();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, sending]);

  // Non-modal by design (spec 6.6): a click outside only dismisses the panel
  // when there is no draft to lose.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (sending) return;
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || fabRef.current?.contains(target)) return;
      if (message.trim() === "") closePanel();
    }
    window.addEventListener("mousedown", onPointerDown);
    return () => window.removeEventListener("mousedown", onPointerDown);
  }, [open, sending, message]);

  // The draft is restored on first open rather than on mount: the panel is
  // always closed after a page load, so this keeps the server-rendered markup
  // and the first client render identical while still surviving a full route
  // navigation.
  function openPanel() {
    // Keep this non-modal panel from competing with account, navigation, or
    // notification controls on compact screens. The event is synchronous, so
    // opening immediately afterward keeps this panel open while peers close.
    emit("close-panels", {});
    if (!restoredRef.current) {
      restoredRef.current = true;
      const draft = readDraft();
      if (draft) {
        setType(draft.type);
        setMessage(draft.message);
      }
    }
    setOpen(true);
  }

  function closePanel() {
    setOpen(false);
    fabRef.current?.focus();
  }

  function onTypeKeyDown(event: React.KeyboardEvent, index: number) {
    const count = TYPES.length;
    let next = index;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (index + 1) % count;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (index - 1 + count) % count;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = count - 1;
    else return;
    event.preventDefault();
    setType(TYPES[next].key);
    typeRefs.current[next]?.focus();
  }

  async function submit() {
    if (sending || submitLocked) return;
    const trimmed = message.trim();
    if (Array.from(trimmed).length < MESSAGE_MIN_LENGTH) return;
    setSending(true);
    setError("");
    try {
      const response = await fetch("/browser-api/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, message: trimmed, path: window.location.pathname }),
      });
      if (!response.ok) {
        const result = await response.json().catch(() => ({}));
        if (response.status === 401) {
          setError("session_expired");
          return;
        }
        setError(result?.error?.code && ERROR_COPY[result.error.code] ? result.error.code : "server");
        return;
      }
      setOpen(false);
      setMessage("");
      setType("idea");
      writeDraft(null);
      showToast({ message: "Thanks — we got it.", kind: "success" });
      fabRef.current?.focus();
      setSubmitLocked(true);
      window.setTimeout(() => setSubmitLocked(false), 2000);
    } catch {
      setError("api_unavailable");
    } finally {
      setSending(false);
    }
  }

  const messageLength = Array.from(message).length;
  // The API accepts feedback without a session (`optional_username`), so a
  // signed-out visitor sends anonymously instead of being sent to log in. A
  // username is attached server-side from the cookie when one exists; the
  // client never sends it.
  const disabled = messageLength < MESSAGE_MIN_LENGTH || sending || submitLocked;
  const hidden = accountOpen || suggestOpen || rivalsDialogOpen;

  return (
    <>
      <button
        ref={fabRef}
        type="button"
        aria-label={open ? "Close feedback" : "Send feedback"}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls="feedback-panel"
        tabIndex={hidden ? -1 : 0}
        onClick={() => (open ? closePanel() : openPanel())}
        className={`fixed bottom-5 right-5 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-[0_6px_20px_rgba(21,93,252,0.30)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-3 focus-visible:outline-blue-600 motion-safe:hover:-translate-y-px motion-safe:active:scale-[0.98] sm:bottom-6 sm:right-6 ${
          hidden ? "hidden" : ""
        }`}
        style={{ marginBottom: "env(safe-area-inset-bottom)" }}
      >
        {open ? <CloseIcon /> : <SpeechBubbleIcon />}
      </button>

      {open && !hidden && (
        <div
          id="feedback-panel"
          ref={panelRef}
          role="dialog"
          aria-modal="false"
          aria-labelledby="feedback-title"
          className="fixed inset-x-4 bottom-[5.25rem] z-40 sm:inset-x-auto sm:bottom-[5.5rem] sm:right-6 sm:w-[22rem]"
        >
          <div className="rounded-[12px] border border-zinc-200 bg-white p-5 shadow-[0_12px_32px_rgba(9,9,11,0.12)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 id="feedback-title" className="text-[1.0625rem] font-bold text-zinc-900">Send feedback</h2>
                <p className="mt-1 text-[0.8125rem] text-zinc-500">Help us make Alpha Poker better.</p>
              </div>
              <button
                type="button"
                aria-label="Close"
                disabled={sending}
                onClick={closePanel}
                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-[5px] text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60"
              >
                <svg aria-hidden="true" viewBox="0 0 16 16" className="h-4 w-4" fill="none">
                  <path d="M3.5 3.5l9 9m0-9-9 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            </div>

            <div role="radiogroup" aria-label="Feedback type" className="mt-4 grid grid-cols-3 gap-2">
              {TYPES.map((option, index) => (
                <button
                  key={option.key}
                  ref={(node) => {
                    typeRefs.current[index] = node;
                  }}
                  type="button"
                  role="radio"
                  aria-checked={type === option.key}
                  tabIndex={type === option.key ? 0 : -1}
                  disabled={sending}
                  onKeyDown={(event) => onTypeKeyDown(event, index)}
                  onClick={() => setType(option.key)}
                  className={`h-9 rounded-[5px] border text-[0.8125rem] font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60 ${
                    type === option.key ? "border-blue-600 bg-blue-600 text-white" : "border-zinc-300 text-zinc-700 hover:bg-zinc-50"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>

            <textarea
              ref={textareaRef}
              rows={4}
              maxLength={MESSAGE_MAX_LENGTH}
              value={message}
              disabled={sending}
              placeholder={TYPES.find((option) => option.key === type)?.placeholder}
              onChange={(event) => setMessage(event.target.value)}
              className="mt-3 min-h-[6rem] w-full resize-y rounded-lg border border-zinc-300 px-3 py-2.5 text-[0.875rem] leading-6 outline-none focus:border-blue-600 focus:ring-2 focus:ring-blue-100 disabled:opacity-60"
            />
            {messageLength > 400 && (
              <p className={`mt-1 text-right text-xs ${messageLength >= MESSAGE_MAX_LENGTH ? "text-red-600" : "text-zinc-400"}`}>
                {messageLength}/{MESSAGE_MAX_LENGTH}
              </p>
            )}

            <p className="mt-2 text-[0.75rem] text-zinc-500">
              {session ? "Sent with your username and this page." : "Sent anonymously with this page address."}
            </p>

            {error && (
              <p role="alert" className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2.5 text-[0.8125rem] text-red-700">
                {error === "session_expired" ? (
                  <>
                    Your session expired.{" "}
                    <button
                      type="button"
                      onClick={() => emit("open-account", {})}
                      className="rounded-[5px] font-semibold text-blue-700 transition-colors hover:text-blue-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
                    >
                      Log in
                    </button>
                  </>
                ) : (
                  ERROR_COPY[error] ?? "Something went wrong on our side. Try again."
                )}
              </p>
            )}

            <button
              type="button"
              disabled={disabled}
              aria-busy={sending}
              onClick={submit}
              className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-[5px] bg-blue-600 text-sm font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-60"
            >
              {sending && (
                <span aria-hidden="true" className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/40 border-t-white motion-reduce:animate-none" />
              )}
              {sending ? "Sending…" : "Send feedback"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
