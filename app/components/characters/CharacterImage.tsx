"use client";
/* eslint-disable @next/next/no-img-element */
import { createContext, useContext, useEffect, useState } from "react";
import { on } from "../uiBus";
import { type Avatar, DEFAULT_AVATAR, safeAvatarUrl } from "./avatar";

const requests = new Map<string, Promise<Avatar | null>>();
export const OfflineCharacters = createContext(false);
function lookup(username: string) {
  let request = requests.get(username);
  if (!request) {
    request = fetch(`/browser-api/avatars/users/${encodeURIComponent(username)}`)
      .then(async r => r.ok ? (await r.json()).avatar as Avatar : null)
      .catch(() => null);
    requests.set(username, request);
  }
  return request;
}
export function CharacterImage({ username, avatar, className = "", alt = "" }: {
  username: string; avatar?: Avatar | null; className?: string; alt?: string;
}) {
  const offline = useContext(OfflineCharacters);
  const [resolved, setResolved] = useState<{ username: string; avatar: Avatar } | null>(null);
  useEffect(() => {
    if (offline) return;
    let active = true;
    if (!avatar && username) void lookup(username).then(value => {
      if (active && value) setResolved({ username, avatar: value });
    });
    const off = on("avatar-changed", detail => {
      if (detail.username !== username) return;
      requests.set(username, Promise.resolve(detail.avatar));
      setResolved({ username, avatar: detail.avatar });
    });
    return () => { active = false; off(); };
  }, [username, avatar, offline]);
  const current = resolved?.username === username ? resolved.avatar : avatar;
  const fallback = offline ? DEFAULT_AVATAR.url.slice(1) : DEFAULT_AVATAR.url;
  const src = offline ? fallback : safeAvatarUrl(current);
  return <img src={src} alt={alt} draggable={false}
    className={`h-full w-full rounded-full object-cover ${className}`}
    onError={event => { if (!event.currentTarget.src.endsWith(fallback)) event.currentTarget.src = fallback; }} />;
}
