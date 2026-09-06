"use client";

import { useEffect, useState } from "react";

type HandEvent = {
  type?: string;
  street?: string;
  action?: string;
  seat?: number;
  paid?: number;
  to?: number;
  board?: string[];
  cards?: string[];
  winner?: string;
  reason?: string;
};
type Hand = {
  players?: string[];
  seat_to_bot?: number[];
  dealer?: number;
  board?: string[];
  pot?: number;
  winner?: string;
  events?: HandEvent[];
};

function playerForSeat(hand: Hand, seat?: number) {
  if (typeof seat !== "number") return null;
  const botIndex = hand.seat_to_bot?.[seat] ?? seat;
  return hand.players?.[botIndex] ?? `Seat ${seat + 1}`;
}

function eventCopy(hand: Hand, event: HandEvent) {
  const player = playerForSeat(hand, event.seat);
  const amount = event.paid ?? event.to;
  if (event.type === "action") {
    return `${player ?? "A player"} ${event.action ?? "acted"}${amount ? ` ${amount.toLocaleString()} play chips` : ""}`;
  }
  if (event.type === "board")
    return `Board: ${(event.cards ?? event.board ?? []).join(" ") || "cards dealt"}`;
  if (event.type === "showdown")
    return `${player ?? "Players"} revealed ${(event.cards ?? []).join(" ") || "their hand"}`;
  if (event.type === "result")
    return event.winner
      ? `${event.winner} won${event.reason ? ` (${event.reason})` : ""}`
      : `Hand ended${event.reason ? ` (${event.reason})` : ""}`;
  return "Another hand event";
}

function eventLabel(event: HandEvent) {
  if (event.type === "action")
    return event.street
      ? event.street[0].toUpperCase() + event.street.slice(1)
      : "Action";
  if (event.type === "board") return "Board";
  if (event.type === "showdown") return "Showdown";
  if (event.type === "result") return "Result";
  return "Hand event";
}

export function HandReplay({ handId }: { handId: string }) {
  const [hand, setHand] = useState<Hand | null>(null);
  const [state, setState] = useState<
    "loading" | "signed-out" | "unavailable" | "ready"
  >("loading");
  useEffect(() => {
    let cancelled = false;
    fetch(`/browser-api/hands/${encodeURIComponent(handId)}`, {
      cache: "no-store",
    })
      .then(async (response) => {
        if (cancelled) return;
        if (response.status === 401) {
          setState("signed-out");
          return;
        }
        if (!response.ok) {
          setState("unavailable");
          return;
        }
        setHand((await response.json()) as Hand);
        setState("ready");
      })
      .catch(() => {
        if (!cancelled) setState("unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [handId]);

  if (state === "loading")
    return (
      <section className="mt-8 rounded-2xl border border-zinc-200 bg-zinc-50 p-6 text-sm text-zinc-600">
        Loading retained hand events…
      </section>
    );
  if (state === "signed-out")
    return (
      <section className="mt-8 rounded-2xl border border-zinc-200 bg-zinc-50 p-6">
        <h2 className="font-semibold">Sign in to view this replay</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          Direct-challenge hand replays are available to challenge participants.
        </p>
      </section>
    );
  if (!hand)
    return (
      <section className="mt-8 rounded-2xl border border-zinc-200 bg-zinc-50 p-6">
        <h2 className="font-semibold">Replay unavailable</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-600">
          This hand may have expired, you may not be a participant, or the local
          API is unavailable.
        </p>
      </section>
    );
  return (
    <>
      <section className="mt-8 grid gap-3 rounded-2xl border border-zinc-200 bg-zinc-50 p-5 sm:grid-cols-3">
        <p>
          <span className="block text-xs font-semibold text-zinc-500">
            PLAYERS
          </span>
          {hand.players?.join(" vs ")}
        </p>
        <p>
          <span className="block text-xs font-semibold text-zinc-500">
            WINNER
          </span>
          {hand.winner ?? "Draw"}
        </p>
        <p>
          <span className="block text-xs font-semibold text-zinc-500">POT</span>
          {hand.pot?.toLocaleString() ?? "-"} play chips
        </p>
      </section>
      <p className="mt-5 text-sm text-zinc-600">
        Dealer: {playerForSeat(hand, hand.dealer) ?? "Not shown"} · Board:{" "}
        {hand.board?.join(" ") || "Not shown"}
      </p>
      <ol className="mt-6 divide-y rounded-2xl border border-zinc-200 bg-white">
        {hand.events?.length ? (
          hand.events.map((event, index) => (
            <li
              key={index}
              className="flex items-center justify-between gap-4 px-5 py-4 text-sm"
            >
              <span>{eventCopy(hand, event)}</span>
              <span className="text-xs font-semibold uppercase tracking-wide text-zinc-500">
                {eventLabel(event)}
              </span>
            </li>
          ))
        ) : (
          <li className="px-5 py-5 text-sm text-zinc-500">
            No retained events are available for this hand.
          </li>
        )}
      </ol>
    </>
  );
}
