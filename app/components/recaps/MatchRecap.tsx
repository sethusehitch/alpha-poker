"use client";
/* eslint-disable react-hooks/set-state-in-effect */

import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
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
  const commits = actor !== null && ["small_blind", "big_blind", "call", "bet", "raise", "all_in"].includes(step.action_kind ?? "") && (step.committed_amount ?? 0) > 0;
  const [arrived, setArrived] = useState(false);
  const [path, setPath] = useState<CSSProperties | null>(null);
  useLayoutEffect(() => {
    if (!commits) return;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    function update() {
      if (motion.matches) { setArrived(true); return; }
      const table = scene.current?.getBoundingClientRect();
      const badge = scene.current?.querySelector(`[data-seat="${actor}"]`)?.getBoundingClientRect();
      const target = pot.current?.querySelector(".pot-chip")?.getBoundingClientRect();
      if (!table || !badge || !target) { setArrived(true); return; }
      setPath({
        "--from-x": `${badge.x + badge.width / 2 - table.x}px`,
        "--from-y": `${(actor === top.seat ? badge.bottom : badge.top) - table.y}px`,
        "--to-x": `${target.x + target.width / 2 - table.x}px`,
        "--to-y": `${target.y + target.height / 2 - table.y}px`,
      } as CSSProperties);
    }
    update();
    motion.addEventListener("change", update);
    window.addEventListener("resize", update);
    return () => { motion.removeEventListener("change", update); window.removeEventListener("resize", update); };
  }, [actor, commits, top.seat]);
  const flying = commits && !arrived;
  const shownPot = flying ? step.pot_before : step.pot;
  return <div ref={scene} className="table-scene" data-actor-seat={actor ?? "none"} data-chip-state={flying ? "flying" : commits ? "settled" : "none"}>
    <div className="scene-label">HAND {hand.hand_number} <span>•</span> STEP {hand.steps.indexOf(step) + 1}/{hand.steps.length}</div><div className="street-label">{step.street}</div>
    <div className="poker-table"><div className="table-line" /><div className="table-wordmark"><AlphaPokerMark /><span>ALPHA POKER</span></div></div>
    <div data-seat={top.seat} className={`seat top-seat ${actor === top.seat ? "seat-active" : ""}`} aria-label={`${top.username}${actor === top.seat ? ", acting player" : ""}`}><BotAvatar name={top.username} circle className="seat-avatar" /><div className="seat-info"><strong>{top.username}</strong><span>{amount(step.stacks[top.seat])} <small>chips</small></span></div><div className="seat-cards"><HoleCards values={step.hole_cards[top.seat] ?? []} /></div>{hand.dealer === top.seat && <span className="dealer">D</span>}</div>
    <div className={`table-action ${actor !== null ? "player-action" : ""}`} title={step.action_label ?? step.summary} aria-live="polite">{step.street === "result" ? "Hand complete" : step.action_label ?? step.summary}</div>
    <div className="board-area"><div ref={pot} className={`pot ${commits ? "pot-receiving" : ""}`} data-pot={shownPot ?? "unknown"}>{commits && <i className={`pot-chip ${arrived ? "chip-arrived" : ""}`} aria-hidden="true" />}<span>{step.street === "result" ? "Pot awarded" : "Pot"}</span><strong>{amount(shownPot)}</strong></div><div className="board">{Array.from({ length: 5 }, (_, slot) => step.board[slot] ? <Card key={slot} value={step.board[slot]} /> : <div key={slot} className="board-slot" aria-label="Not dealt" />)}</div></div>
    <div data-seat={bottom.seat} className={`seat bottom-seat ${actor === bottom.seat ? "seat-active" : ""}`} aria-label={`${bottom.username}${actor === bottom.seat ? ", acting player" : ""}`}><div className="hero-cards"><HoleCards values={step.hole_cards[bottom.seat] ?? []} /></div><BotAvatar name={bottom.username} circle className="seat-avatar" /><div className="seat-info"><strong>{bottom.username} {bottom.is_viewer && <small className="seat-you">You</small>}</strong><span>{amount(step.stacks[bottom.seat])} <small>chips</small></span></div>{hand.dealer === bottom.seat && <span className="dealer bottom-dealer">D</span>}</div>
    {flying && path && <div className="chip-flight" style={path} aria-hidden="true" onAnimationEnd={event => { if (event.animationName === "recap-chip-flight") setArrived(true); }}><i /><small>+{amount(step.committed_amount)}</small></div>}
    <div className="table-foot">Play chips · Stacks reset each hand</div>
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

export function RecapView({ data, initialHandId }: { data: Recap; initialHandId?: string }) {
  const [index, setIndex] = useState(Math.max(0, data.highlights.findIndex(h => h.hand_id === initialHandId)));
  const hand = data.highlights[index];
  const [stepIndex, setStepIndex] = useState(hand ? hand.steps.length - 1 : 0);
  const [playing, setPlaying] = useState(false);
  const [visit, setVisit] = useState(0);
  useEffect(() => {
    if (!playing || !hand) return;
    if (stepIndex >= hand.steps.length - 1) { setPlaying(false); return; }
    const timer = window.setTimeout(() => setStepIndex(step => step + 1), STEP_INTERVAL_MS);
    return () => window.clearTimeout(timer);
  }, [playing, hand, stepIndex]);
  function select(next: number) {
    setPlaying(false);
    setIndex(next);
    setStepIndex(data.highlights[next].steps.length - 1);
    setVisit(value => value + 1);
    const url = new URL(window.location.href);
    url.searchParams.set("hand", data.highlights[next].hand_id);
    window.history.replaceState(window.history.state, "", url);
  }
  function selectStep(next: number) {
    setPlaying(false);
    setStepIndex(next);
    setVisit(value => value + 1);
  }
  const back = data.challenge ? `/rivals?rival=${encodeURIComponent(data.challenge.opponent_username ?? data.players[1])}&result=${encodeURIComponent(data.challenge.challenge_id)}` : "/leaderboard";
  if (!hand) return <main className="recap-message"><a href={back}>← Back to results</a><section><h1>No retained hands</h1><p>The match completed, but detailed hand records are no longer available. Check the match artifact if one was saved.</p></section></main>;
  const step = hand.steps[stepIndex] ?? hand.steps[hand.steps.length - 1];
  const bottom = hand.players.find(p => p.is_viewer) ?? hand.players[0];
  const top = hand.players.find(p => p.seat !== bottom.seat)!;
  const profit = bottom.profit;
  const won = profit != null && profit > 0;
  const tied = hand.winners.length === 2;
  const outcomeLabel = tied ? "Split pot" : profit == null ? "Net result" : `${bottom.is_viewer ? "You" : bottom.username} ${won ? "won" : profit < 0 ? "lost" : "net"}`;
  return <div className="replay-page"><main className="replay-main">
    <a href={back} className="back-link">← <span>Back to {data.challenge ? "recap" : "results"}</span></a>
    <div className="page-heading"><div><h1>{data.source === "direct_challenge" ? "Rivalry recap" : "Match recap"}</h1><p>{data.players[0]} <span>vs</span> {data.players[1]}</p></div><span className="replay-label"><i /> {data.source === "direct_challenge" ? "Direct challenge" : "Round robin"}</span></div>
    {!data.complete_history && <p className="retention-note" role="status">Showing {data.retained_hands} retained hands from {data.total_hands}. Match-wide lead changes cannot be determined from partial history.</p>}
    <div className="replay-layout"><aside className="replay-sidebar">
      <div className="highlight"><div className="highlight-label">↗ {hand.label}</div><div className={`win-label ${won ? "" : profit != null && profit < 0 ? "loss-label" : "neutral-label"}`}>{outcomeLabel}<strong>{profit == null ? "Not retained" : `${profit > 0 ? "+" : ""}${amount(profit)}`}</strong></div><span className="highlight-note">Net play chips</span></div>
      <div className="hand-selector"><button aria-label="Previous highlight" disabled={index === 0} onClick={() => select(index - 1)}><Arrow /></button><strong>Highlight {index + 1} <span>of {data.highlights.length}</span></strong><button aria-label="Next highlight" disabled={index === data.highlights.length - 1} onClick={() => select(index + 1)}><Arrow right /></button></div>
      <div className="player-list"><PlayerSummary player={bottom} /><PlayerSummary player={top} /></div><div className="sidebar-note">Hand {hand.hand_number} of {data.total_hands}</div>
    </aside>
    <section className="replay-stage" aria-label={`Hand ${hand.hand_number} replay`}>
      <ReplayTable key={`${hand.hand_id}:${stepIndex}:${visit}`} hand={hand} step={step} bottom={bottom} top={top} />
      <div className="playback"><div className="timeline" aria-label="Highlights">{data.highlights.map((h, i) => <button key={h.hand_id} aria-label={`Highlight ${i + 1}: ${h.label}`} aria-current={i === index ? "step" : undefined} className={i === index ? "active" : i > index ? "remaining" : ""} onClick={() => select(i)} />)}</div><div className="playback-row"><span className="playback-status">Hand {hand.hand_number} of {data.total_hands}</span><div className="playback-buttons"><button aria-label="Previous action" disabled={stepIndex === 0} onClick={() => selectStep(stepIndex - 1)}><Arrow /><span>Previous</span></button><button className="play-button" disabled={hand.steps.length < 2} onClick={() => { if (!playing && stepIndex === hand.steps.length - 1) setStepIndex(0); setPlaying(!playing); }}><span aria-hidden="true">{playing ? "Ⅱ" : "▶"}</span>{playing ? "Pause" : "Play"}</button><button aria-label="Next action" disabled={stepIndex === hand.steps.length - 1} onClick={() => selectStep(stepIndex + 1)}><span>Next</span><Arrow right /></button></div><span className="speed">Step {stepIndex + 1} / {hand.steps.length}</span></div></div>
      <div className="action-summary" aria-live="polite"><span>{step.street === "result" ? "Result" : "Last action"}</span><p>{step.summary}</p></div>
      <details className="recap-events"><summary>Hand actions ({hand.steps.length})</summary><ol>{hand.steps.map((s, i) => <li key={i}><button aria-current={i === stepIndex ? "step" : undefined} onClick={() => selectStep(i)}><span>{s.street}</span>{s.summary}</button></li>)}</ol><p>Previous and Next step through actions. Use the highlight bar to switch hands. Only your cards and cards revealed at showdown are shown. Missing retained values are left unavailable.</p></details>
    </section></div></main></div>;
}
