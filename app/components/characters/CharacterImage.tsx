"use client";
/* eslint-disable @next/next/no-img-element */
import { useEffect, useState } from "react";
import { on } from "../uiBus";
import { type Avatar, DEFAULT_AVATAR, safeAvatarUrl } from "./avatar";

const requests = new Map<string, Promise<Avatar | null>>();
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
  const [resolved, setResolved] = useState<{ username: string; avatar: Avatar } | null>(null);
  useEffect(() => {
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
  }, [username, avatar]);
  const current = resolved?.username === username ? resolved.avatar : avatar;
  return <img src={safeAvatarUrl(current)} alt={alt} draggable={false}
    className={`h-full w-full rounded-full object-cover ${className}`}
    onError={event => { if (!event.currentTarget.src.endsWith(DEFAULT_AVATAR.url)) event.currentTarget.src = DEFAULT_AVATAR.url; }} />;
}
