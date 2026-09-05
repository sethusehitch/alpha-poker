export function AlphaPokerMark({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={className}
      viewBox="0 0 42 34"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path
        d="M9.25 5.75 2.75 17l6.5 11.25M32.75 5.75 39.25 17l-6.5 11.25"
        stroke="#1768FF"
        strokeWidth="3.25"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M29.31 18.33c0-4.96-8.31-11.43-8.31-11.43s-8.31 6.47-8.31 11.43c0 3.48 2.5 5.96 5.58 5.96.53 0 1.03-.08 1.51-.23-.31 2.3-1.2 4.02-2.64 5.5h7.72c-1.44-1.48-2.33-3.2-2.64-5.5.48.15.98.23 1.51.23 3.08 0 5.58-2.48 5.58-5.96Z"
        fill="#0A0A0B"
      />
      <path d="m21 23.1-3.35 6.46h6.7L21 23.1Z" fill="#1768FF" />
    </svg>
  );
}
