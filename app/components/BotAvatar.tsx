import { CharacterImage } from "./characters/CharacterImage";
import type { Avatar } from "./characters/avatar";
/** Account-owned character. Rank never changes the chosen character. */
export function BotAvatar({ name, circle = false, className = "", avatar }: {
  name: string; rank?: number; circle?: boolean; className?: string; avatar?: Avatar | null;
}) {
  return <span aria-hidden="true" data-robot={name}
    className={`relative grid h-14 w-14 shrink-0 overflow-hidden bg-white ${circle ? "rounded-full ring-2 ring-white shadow-sm" : "rounded-2xl"} ${className}`}>
    <CharacterImage username={name} avatar={avatar} />
  </span>;
}
