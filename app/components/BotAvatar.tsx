// One shared sprite crop for every bot portrait in the signed-in app (rival
// cards, the rival overlay, and /my-bot) so the same player always reads as the
// same character across surfaces.
export function BotAvatar({
  name,
  rank,
  circle = false,
  className = "",
}: {
  name: string;
  rank?: number;
  /** Rivals portraits read as characters, so they crop to a circle. */
  circle?: boolean;
  className?: string;
}) {
  const hash = Array.from(name).reduce(
    (total, letter) => total + letter.codePointAt(0)!,
    0,
  );
  const position = ["0% 43%", "50% 43%", "100% 43%"][
    Math.abs((rank ?? hash) % 3)
  ];
  const shape = circle
    ? "rounded-full ring-2 ring-white shadow-[0_6px_18px_rgba(23,35,70,0.12)]"
    : "rounded-2xl shadow-inner ring-1 ring-blue-100";
  return (
    <span
      aria-hidden="true"
      data-robot={name}
      className={`relative grid h-14 w-14 shrink-0 overflow-hidden bg-gradient-to-br from-blue-100 via-white to-violet-100 ${shape} ${className}`}
    >
      <span
        className="absolute inset-0 bg-no-repeat"
        style={{
          backgroundImage: "url('/robot-avatars.png?v=poker-kids-1')",
          backgroundPosition: position,
          backgroundSize: "300% auto",
        }}
      />
    </span>
  );
}
