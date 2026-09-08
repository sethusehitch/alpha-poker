export type Avatar = { id: string; url: string };
export const DEFAULT_AVATAR: Avatar = { id: "elephant", url: "/characters/elephant.webp" };
export const PRESETS = ["elephant", "bear", "octopus", "bird"] as const;
export function safeAvatarUrl(avatar?: Avatar | null) {
  const url = avatar?.url ?? "";
  return /^\/characters\/(elephant|bear|octopus|bird)\.webp$/.test(url) ||
    /^\/browser-api\/avatars\/[a-f0-9]{64}$/.test(url) ? url : DEFAULT_AVATAR.url;
}
