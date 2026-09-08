"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { BotAvatar } from "../BotAvatar";
import { AlphaPokerMark } from "../AlphaPokerMark";
import { useSession } from "../useSession";
import type { Highlight, MatchRecap as Recap, ReplayPlayer, ReplayStep } from "./types";
import "./recap.css";

const amount = (value: number | null | undefined) => value == null ? "Not retained" : value.toLocaleString();
const STEP_INTERVAL_MS = 2200;
const suits: Record<string, string> = { s: "♠", h: "♥", d: "♦", c: "♣" };
function Arrow({ right = false }: { right?: boolean }) {
  return <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d={right ? "m7 4 6 6-6 6" : "m13 4-6 6 6 6"} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>;
}
function Card({ value }: { value?: string }) {
  const rank = value?.[0] === "T" ? "10" : value?.[0];
  const suit = suits[value?.[1] ?? ""];
  return <div className={`playing-card ${value?.[1] === "d" || value?.[1] === "h" ? "red" : ""} ${value ? "" : "card-back"}`} aria-label={value ? `${rank}${suit}` : "Hidden card"}>
    {value ? <><div className="card-corner">{rank}<span>{suit}</span></div><span className="card-suit">{suit}</span><div className="card-bottom">{rank}<span>{suit}</span></div></> : <span>♠</span>}
  </div>;
}
function HoleCards({ values }: { values: string[] }) {
  return <><Card value={values[0]} /><Card value={values[1]} /></>;
}
function WinChance({ step, seat }: { step: ReplayStep; seat: number }) {
  const equity = step.equity?.version === "showdown-equity-v1" ? step.equity : null;
  const value = equity?.percentages[seat];
  const estimated = equity?.method === "estimated";
  const label = value == null ? "Win chance unavailable. Both hands must be revealed at a completed showdown." : `Win chance ${value} percent${estimated ? ", estimated" : ", exact"}. Retrospective showdown equity; ties count half.${estimated ? ` Based on ${amount(equity?.trials)} sampled boards${equity?.sampling_error_pp != null ? `, approximately ±${equity.sampling_error_pp} percentage points at 95% confidence` : ""}.` : ""}`;
  return <span className="seat-equity" data-equity={value ?? "unknown"} data-method={equity?.method ?? "unavailable"} aria-label={label} title={label}>Win chance <b>{value == null ? "—" : `${value}%`}</b>{estimated && <small>estimated</small>}</span>;
}
function PlayerSummary({ player }: { player: ReplayPlayer }) {
  return <div className={`player-summary ${player.is_viewer ? "hero" : "opponent"}`}>
    <div className="player-name"><BotAvatar name={player.username} circle /><div><strong>{player.username}</strong><span>{player.is_viewer ? "Your bot" : "Opponent"}</span></div>{player.is_viewer && <small className="you-tag">You</small>}</div>
    <div className="player-bottom"><div><strong>{amount(player.final_stack)}</strong><span>After this hand</span></div><div className="mini-cards"><HoleCards values={player.hole_cards} /></div></div>
    <span className="profit-note">Net {player.profit == null ? "not retained" : `${player.profit > 0 ? "+" : ""}${amount(player.profit)}`} play chips</span>
  </div>;
}

// A fresh presentation for each visited step owns its animation. Unmounting on
// manual navigation or hand selection discards the old flight, never a pot delta.
function ReplayTable({ hand, step, bottom, top }: { hand: Highlight; step: ReplayStep; bottom: ReplayPlayer; top: ReplayPlayer }) {
  const scene = useRef<HTMLDivElement>(null);
  const pot = useRef<HTMLDivElement>(null);
  const actor = step.street !== "result" && step.street !== "showdown" && (step.actor_seat === 0 || step.actor_seat === 1) ? step.actor_seat : null;
  const chips = step.table_chips?.version === "street-wagers-v1" ? step.table_chips : null;
  const sweeping = chips?.phase === "sweep";
  const transfers = useMemo(() => {
    if (!chips) return [];
    if (chips.phase === "sweep") return chips.sweep.flatMap((paid, seat) => paid != null && paid > 0 ? [{ seat, paid }] : []);
    return chips.phase === "payment" && actor !== null && (step.committed_amount ?? 0) > 0 ? [{ seat: actor, paid: step.committed_amount! }] : [];
  }, [chips, actor, step.committed_amount]);
  const [arrived, setArrived] = useState(false);
  const completed = useRef(new Set<number>());
  const [paths, setPaths] = useState<{ seat: number; paid: number; style: CSSProperties }[]>([]);
  useLayoutEffect(() => {
    if (!transfers.length) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    function update() {
      if (motion.matches) { setArrived(true); return; }
      const table = scene.current?.getBoundingClientRect();
      if (!table) { setArrived(true); return; }
      const next = transfers.flatMap(({ seat, paid }) => {
        const badge = scene.current?.querySelector(`[data-seat="${seat}"]`)?.getBoundingClientRect();
        const wager = scene.current?.querySelector(`[data-wager-seat="${seat}"] .wager-chip`)?.getBoundingClientRect();
        const center = pot.current?.querySelector(".pot-chip")?.getBoundingClientRect();
        const source = sweeping ? wager : badge;
        const target = sweeping ? center : wager;
        if (!source || !target) return [];
        return [{ seat, paid, style: {
          "--from-x": `${source.x + source.width / 2 - table.x}px`,
          "--from-y": `${(sweeping ? source.y + source.height / 2 : seat === top.seat ? source.bottom : source.top) - table.y}px`,
          "--to-x": `${target.x + target.width / 2 - table.x}px`,
          "--to-y": `${target.y + target.height / 2 - table.y}px`,
        } as CSSProperties }];
      });
      if (next.length !== transfers.length) { setArrived(true); return; }
      setPaths(next);
    }
    update();
    motion.addEventListener("change", update);
    window.addEventListener("resize", update);
    return () => { motion.removeEventListener("change", update); window.removeEventListener("resize", update); };
  }, [transfers, sweeping, top.seat]);
  const flying = transfers.length > 0 && !arrived;
  // A legacy payload has a total pot, not enough evidence for a street ledger.
  // Show it honestly without inventing contributions or direct-to-pot flights.
  const shownPot = chips ? flying && sweeping ? chips.gathered_before : chips.gathered_pot : step.pot;
  const wagers = chips ? flying ? chips.wagers_before : chips.wagers : [];
  const final = step.street === "result";
  const split = hand.winners.length === 2;
  const winner = (player: ReplayPlayer) => final && hand.winners.includes(player.username);
  const resultLabel = split ? "Split pot" : hand.winners.length === 1 ? `${hand.winners[0]} wins` : hand.outcome;
  return <div ref={scene} className="table-scene" data-hand-id={hand.hand_id} data-step-index={hand.steps.indexOf(step)} data-actor-seat={actor ?? "none"} data-chip-state={flying ? sweeping ? "sweeping" : "flying" : transfers.length ? "settled" : "none"}>
    <div className="scene-label">{hand.game_number ? `GAME ${hand.game_number} · ` : ""}HAND {hand.hand_number} <span>•</span> STEP {hand.steps.indexOf(step) + 1}/{hand.steps.length}</div><div className="street-label">{step.street}</div>
    <div className="poker-table"><div className="table-line" /><div className="table-wordmark"><AlphaPokerMark /><span>ALPHA POKER</span></div></div>
    <div data-seat={top.seat} className={`seat top-seat ${actor === top.seat ? "seat-active" : ""} ${winner(top) ? "seat-winner" : ""}`} aria-label={`${top.username}${actor === top.seat ? ", acting player" : winner(top) ? split ? ", split pot" : ", winner" : ""}`}><BotAvatar name={top.username} circle className="seat-avatar" /><div className="seat-info"><strong>{top.username}</strong><span>{amount(step.stacks[top.seat])} <small>chips</small></span><WinChance step={step} seat={top.seat} /></div>{winner(top) && <span className="seat-result">{split ? "Split pot" : "Winner"}</span>}<div className="seat-cards"><HoleCards values={step.hole_cards[top.seat] ?? []} /></div>{hand.dealer === top.seat && <span className="dealer">D</span>}</div>
    <div className={`table-action ${actor !== null ? "player-action" : ""} ${final && hand.winners.length ? "result-action" : ""}`} title={step.action_label ?? step.summary} aria-label={step.action_label ?? step.summary} aria-live="polite">{final ? resultLabel : step.action_label ?? step.summary}</div>
    <div className="board-area"><div ref={pot} className={`pot ${final && hand.winners.length ? "pot-awarded" : ""}`} data-pot={shownPot ?? "unknown"}>{chips && <i className={`pot-chip ${(shownPot ?? 0) > 0 ? "chip-arrived" : ""}`} aria-hidden="true" />}<span>{final ? "Pot awarded" : chips ? "Gathered pot" : "Total pot"}</span><strong>{amount(shownPot)}</strong></div><div className="board">{Array.from({ length: 5 }, (_, slot) => step.board[slot] ? <Card key={slot} value={step.board[slot]} /> : <div key={slot} className="board-slot" aria-label="Not dealt" />)}</div></div>
    <div data-seat={bottom.seat} className={`seat bottom-seat ${actor === bottom.seat ? "seat-active" : ""} ${winner(bottom) ? "seat-winner" : ""}`} aria-label={`${bottom.username}${actor === bottom.seat ? ", acting player" : winner(bottom) ? split ? ", split pot" : ", winner" : ""}`}><div className="hero-cards"><HoleCards values={step.hole_cards[bottom.seat] ?? []} /></div><BotAvatar name={bottom.username} circle className="seat-avatar" /><div className="seat-info"><strong>{bottom.username} {bottom.is_viewer && <small className="seat-you">You</small>}</strong><span>{amount(step.stacks[bottom.seat])} <small>chips</small></span><WinChance step={step} seat={bottom.seat} /></div>{winner(bottom) && <span className="seat-result">{split ? "Split pot" : "Winner"}</span>}{hand.dealer === bottom.seat && <span className="dealer bottom-dealer">D</span>}</div>
    {chips && [top, bottom].map(player => <div key={player.seat} data-wager-seat={player.seat} data-wager={wagers[player.seat] ?? "unknown"} className={`seat-wager ${player.seat === top.seat ? "top-wager" : "bottom-wager"} ${wagers[player.seat] === 0 ? "empty-wager" : ""} ${flying && sweeping ? "wager-sweeping" : ""}`} aria-label={`${player.username} wager: ${amount(wagers[player.seat])}`}><i className="wager-chip" aria-hidden="true" /><span>Wager <strong>{wagers[player.seat] == null ? "—" : amount(wagers[player.seat])}</strong></span></div>)}
    {flying && paths.map(path => <div key={path.seat} className={`chip-flight ${sweeping ? "chip-sweep" : "chip-payment"}`} data-flight-seat={path.seat} style={path.style} aria-hidden="true" onAnimationEnd={event => { if (event.animationName === "recap-chip-flight") { completed.current.add(path.seat); if (completed.current.size === transfers.length) setArrived(true); } }}><i /><small>{sweeping ? "" : "+"}{amount(path.paid)}</small></div>)}
  </div>;
}

export function MatchRecap({ endpoint, initialHandId }: { endpoint: string; initialHandId?: string }) {
  const { session, loaded } = useSession();
  const viewer = session?.username ?? "";
  const [result, setResult] = useState<{ key: string; data?: Recap; status?: number } | null>(null);
  const [attempt, setAttempt] = useState(0);
  const requestKey = `${endpoint}:${viewer}`;
  useEffect(() => {
    if (!loaded) return;
    const controller = new AbortController();
    setResult(null);
    fetch(endpoint, { cache: "no-store", signal: controller.signal })
      .then(async response => {
        const data = response.ok ? await response.json() : undefined;
        if (!controller.signal.aborted) setResult({ key: requestKey, data, status: response.status });
      })
      .catch(() => { if (!controller.signal.aborted) setResult({ key: requestKey, status: 503 }); });
    return () => controller.abort();
  }, [endpoint, requestKey, loaded, attempt]);
  const current = result?.key === requestKey ? result : null;
  if (current?.data?.schema_version === "recap-v1") return <RecapView key={requestKey} data={current.data} initialHandId={initialHandId} />;
  const title = !current ? "Loading recap…" : current.status === 401 ? "Sign in to view this recap" : current.status === 403 ? "This recap is private" : current.status === 409 ? "This match is still in progress" : "Recap unavailable";
  const detail = current?.status === 401 || current?.status === 403 ? "Direct challenge recaps are available to the two participants. Use the sign-in button above." : current?.status === 409 ? "Return when the match has completed." : "The retained match record may have expired, or the API may be unavailable.";
  return <main className="recap-message"><a href="/rivals">← Back to Rivals</a><section role={current ? "status" : undefined} aria-busy={!current}><h1>{title}</h1>{current && <><p>{detail}</p><button onClick={() => setAttempt(a => a + 1)}>Try again</button></>}</section></main>;
}

export function RecapView({ data, initialHandId, backHref, selectionLabel = "Highlight" }: { data: Recap; initialHandId?: string; backHref?: string | null; selectionLabel?: string }) {
  const [index, setIndex] = useState(Math.max(0, data.highlights.findIndex(h => h.hand_id === initialHandId)));
  const hand = data.highlights[index];
  const [stepIndex, setStepIndex] = useState(hand ? hand.steps.length - 1 : 0);
  const [playing, setPlaying] = useState(false);
  const [visit, setVisit] = useState(0);
  const [intro, setIntro] = useState(false);
  function updateHandUrl(next: number) {
    const url = new URL(window.location.href);
    url.searchParams.set("hand", data.highlights[next].hand_id);
    window.history.replaceState(window.history.state, "", url);
  }
  useEffect(() => {
    if (!playing || !hand || intro) return;
    const timer = window.setTimeout(() => {
      if (stepIndex < hand.steps.length - 1) setStepIndex(step => step + 1);
      else if (index < data.highlights.length - 1) {
        const next = index + 1;
        setIndex(next);
        setStepIndex(0);
        setIntro(true);
        setVisit(value => value + 1);
        const url = new URL(window.location.href);
        url.searchParams.set("hand", data.highlights[next].hand_id);
        window.history.replaceState(window.history.state, "", url);
      } else setPlaying(false);
    }, stepIndex === hand.steps.length - 1 ? 1500 : STEP_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [playing, hand, stepIndex, visit, intro, index, data.highlights]);
  function select(next: number) {
    setPlaying(false);
    setIntro(false);
    setIndex(next);
    setStepIndex(data.highlights[next].steps.length - 1);
    setVisit(value => value + 1);
    updateHandUrl(next);
  }
  function replayHand() {
    setPlaying(true);
    setStepIndex(0);
    setVisit(value => value + 1);
    setIntro(true);
  }
  const back = data.challenge ? `/rivals?rival=${encodeURIComponent(data.challenge.opponent_username ?? data.players[1])}` : "/leaderboard";
  if (!hand) return <main className="recap-message"><a href={back}>← Back to results</a><section><h1>No retained hands</h1><p>The match completed, but detailed hand records are no longer available. Check the match artifact if one was saved.</p></section></main>;
  const step = hand.steps[stepIndex] ?? hand.steps[hand.steps.length - 1];
  const bottom = hand.players.find(p => p.is_viewer) ?? hand.players[0];
  const top = hand.players.find(p => p.seat !== bottom.seat)!;
  return <div className="replay-page"><main className="replay-main">
    {backHref !== null && <a href={backHref ?? back} className="back-link"><span className="back-arrow" aria-hidden="true">←</span><span>Back</span></a>}
    {!data.complete_history && <p className="retention-note" role="status">Showing {data.retained_hands} retained hands from {data.total_hands}. Match-wide lead changes cannot be determined from partial history.</p>}
    <div className="replay-layout"><aside className="replay-sidebar" aria-label="Recap controls and hand result">
      <div className="player-list"><PlayerSummary player={bottom} /><PlayerSummary player={top} /></div>
      <div className="hand-selector"><button aria-label="Previous highlight" disabled={index === 0} onClick={() => select(index - 1)}><Arrow /></button><strong>{selectionLabel === "Hand" ? `Hand ${hand.hand_number}` : <>{selectionLabel} {index + 1} <span>of {data.highlights.length}</span></>}</strong><button aria-label="Next highlight" disabled={index === data.highlights.length - 1} onClick={() => select(index + 1)}><Arrow right /></button></div>
      <div className="hand-playback" role="group" aria-label="Hand playback"><button className="replay-button" disabled={hand.steps.length < 2} onClick={replayHand}><svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 8a6 6 0 1 1 0 4M4 3v5h5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" /></svg>Replay</button><button className="play-button" disabled={hand.steps.length < 2} onClick={() => { if (!playing && stepIndex === hand.steps.length - 1) replayHand(); else setPlaying(!playing); }}><span aria-hidden="true">{playing ? "Ⅱ" : "▶"}</span>{playing ? "Pause" : "Play"}</button></div>
    </aside>
    <section className="replay-stage" aria-label={`Hand ${hand.hand_number} replay`}>
      <ReplayTable key={`${hand.hand_id}:${stepIndex}:${visit}`} hand={hand} step={step} bottom={bottom} top={top} />
      {intro && <div className="hand-intro" role="status" aria-label={`${hand.label}. ${hand.game_number ? `Game ${hand.game_number}. ` : ""}Hand ${hand.hand_number}${hand.game_number ? "" : ` of ${data.total_hands}`}`}>
        <div key={`${hand.hand_id}:${visit}`} className="hand-intro-flight" style={{ animationPlayState: playing ? "running" : "paused" }} onAnimationEnd={event => { if (event.target === event.currentTarget) setIntro(false); }}>
          <div className="hand-intro-banner"><strong>{hand.label}</strong><span>{hand.game_number ? `Game ${hand.game_number} · Hand ${hand.hand_number}` : `Hand ${hand.hand_number} of ${data.total_hands}`}</span><div className="hand-intro-match">{data.players[0]} <small>vs</small> {data.players[1]}</div></div>
        </div>
      </div>}
    </section></div></main></div>;
}
