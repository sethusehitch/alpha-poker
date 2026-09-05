"use client";

import { useEffect, useRef, useState } from "react";

export function CopyPromptButton({
  text,
  label = "Copy prompt",
}: {
  text: string;
  label?: string;
}) {
  const [copied, setCopied] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  async function handleCopy() {
    let didCopy = false;

    try {
      await navigator.clipboard.writeText(text);
      didCopy = true;
    } catch {
      // Local HTTP and embedded browsers may not expose the Clipboard API. Keep a
      // synchronous fallback so the button still works in the local-first MVP.
      const textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      didCopy = document.execCommand("copy");
      textarea.remove();
    }

    if (didCopy) {
      setCopied(true);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(() => setCopied(false), 3000);
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex min-h-11 shrink-0 items-center justify-center gap-2 rounded-[5px] bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white shadow-[0_1px_2px_rgba(0,0,0,0.08)] transition-colors hover:bg-blue-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600"
    >
      <svg
        aria-hidden="true"
        viewBox="0 0 20 20"
        fill="none"
        className="h-4 w-4"
      >
        <rect
          x="6.5"
          y="6.5"
          width="10"
          height="11"
          rx="1.5"
          stroke="currentColor"
          strokeWidth="1.5"
        />
        <path
          d="M4 12.5V4.5A1.5 1.5 0 0 1 5.5 3h8"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
      {copied ? "Copied" : label}
      <span className="sr-only" role="status" aria-live="polite">
        {copied ? "Prompt copied to clipboard" : ""}
      </span>
    </button>
  );
}
