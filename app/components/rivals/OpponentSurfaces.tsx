"use client";
import type { ReactNode } from "react";
import { BotAvatar } from "../BotAvatar";

export function Portrait({ name, avatar, rank, className }: {
  name: string; avatar?: {id: string; url: string}; rank?: number | null; className: string;
}) {
  return <span className="relative inline-flex shrink-0">
    <span aria-hidden="true" className="absolute -inset-1.5 rounded-full bg-[radial-gradient(circle_at_35%_30%,#e0ecff,transparent_70%)]" />
    <BotAvatar name={name} avatar={avatar} rank={rank ?? undefined} circle className={`relative ${className}`} />
  </span>;
}

// Shared with Rivals: keep the established proportions, borders and selection.
export function OpponentCardSurface({ selected = false, children }: { selected?: boolean; children: ReactNode }) {
  return <article className={`flex h-[18.5rem] min-h-0 w-full max-w-[20.5625rem] flex-col justify-between overflow-hidden rounded-2xl border bg-white p-4 shadow-[0_8px_28px_rgba(23,35,70,0.04)] transition hover:shadow-[0_12px_32px_rgba(23,35,70,0.08)] ${selected ? "border-blue-500 ring-1 ring-blue-500/20" : "border-zinc-200 hover:border-blue-300"}`}>{children}</article>;
}

export const OPPONENT_BACKDROP = "fixed inset-0 z-50 flex items-end justify-end bg-zinc-950/25 p-0 sm:p-4";
export const OPPONENT_PANEL = "relative flex h-[92dvh] max-h-[100dvh] w-full max-w-[29rem] flex-col overflow-hidden rounded-t-2xl bg-white p-5 shadow-2xl outline-none sm:h-[calc(100dvh-2rem)] sm:max-h-[calc(100dvh-2rem)] sm:rounded-2xl sm:p-7";
