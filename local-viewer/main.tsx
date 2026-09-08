import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { RecapView } from "../app/components/recaps/MatchRecap";
import { AlphaPokerMark } from "../app/components/AlphaPokerMark";
import { OfflineCharacters } from "../app/components/characters/CharacterImage";
import type { MatchRecap } from "../app/components/recaps/types";
import "../app/globals.css";
import "./style.css";

type Group = { id: string; name: string; hands: {id: string; number: number; game: number | null}[] };
function LocalViewer() {
  const [manifest, setManifest] = useState<{name: string; groups: Group[]; warnings: string[]} | null>(null);
  const [group, setGroup] = useState("");
  const [hand, setHand] = useState("");
  const [result, setResult] = useState<{key: string; data: MatchRecap} | null>(null);
  const [error, setError] = useState("");
  const key = `${group}/${hand}`;
  useEffect(() => {
    fetch("manifest.json").then(r => { if (!r.ok) throw Error("Local recap is no longer available. Run the recap command again."); return r.json(); })
      .then(data => {setManifest(data); setGroup(data.groups[0].id);}).catch(e => setError(e.message));
  }, []);
  useEffect(() => {
    if (!group) return;
    const controller = new AbortController();
    fetch(`recap/${group}${hand ? `/${hand}` : ""}`, {signal: controller.signal}).then(r => {
      if (!r.ok) throw Error("Could not load this hand. Restart the recap command to try again.");
      return r.json();
    }).then(data => {setResult({key, data}); setError("");}).catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [group, hand, key]);
  const selected = manifest?.groups.find(g => g.id === group);
  return <><header className="local-header"><AlphaPokerMark/><strong>Alpha Poker</strong><span>Local recap</span></header>
    <div className="local-tools"><span title={manifest?.name}>{manifest?.name}</span>
      {manifest && manifest.groups.length > 1 && <label>Match <select aria-label="Match" value={group} onChange={e => {setGroup(e.target.value); setHand("");}}>{manifest.groups.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></label>}
      {selected && <label>View <select aria-label="Choose hand" value={hand} onChange={e => setHand(e.target.value)}><option value="">Highlights</option>{selected.hands.map(h => <option key={h.id} value={h.id}>{h.game ? `Game ${h.game} · ` : ""}Hand {h.number}</option>)}</select></label>}
    </div>
    {manifest?.warnings.map(w => <p className="local-notice" key={w}>{w}</p>)}
    {error ? <p role="alert" className="local-notice">{error}</p> : result?.key === key ? <RecapView key={key} data={result.data} backHref={null} selectionLabel={hand ? "Hand" : "Highlight"}/> : <p role="status" className="local-notice">Loading recap…</p>}
  </>;
}
createRoot(document.getElementById("root")!).render(<OfflineCharacters.Provider value={true}><LocalViewer/></OfflineCharacters.Provider>);
