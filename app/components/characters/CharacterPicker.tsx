"use client";

import { useEffect, useId, useRef, useState, type PointerEvent } from "react";
import { cropGeometry, exportCrop, inspectUpload, type CropImage } from "./imageCrop";

export type CharacterAvatar = { id: string; url: string };
type Props = { initialAvatar: CharacterAvatar; onSaved: (avatar: CharacterAvatar) => void; onSkip?: () => void; onPendingChange?: (pending: boolean) => void; saveDraft?: (avatar: CharacterAvatar) => Promise<CharacterAvatar>; saveLabel?: string; compact?: boolean };
const presets = ["elephant", "bear", "octopus", "bird"] as const;
const names: Record<string, string> = { elephant: "Elephant", bear: "Bear", octopus: "Octopus", bird: "Bird" };

export function CharacterPicker({ initialAvatar, onSaved, onSkip, onPendingChange, saveDraft, saveLabel, compact = false }: Props) {
  const [draft, setDraft] = useState(initialAvatar);
  const [custom, setCustom] = useState<CharacterAvatar | null>(presets.some(id => id === initialAvatar.id) ? null : initialAvatar);
  const [crop, setCrop] = useState<CropImage | null>(null);
  const [zoom, setZoom] = useState(1);
  const [x, setX] = useState(50);
  const [y, setY] = useState(50);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const uploadButton = useRef<HTMLButtonElement>(null);
  const cropTitle = useRef<HTMLHeadingElement>(null);
  const preview = useRef<HTMLDivElement>(null);
  const blob = useRef<string | null>(null);
  const mounted = useRef(true);
  const lock = useRef(false);
  const drag = useRef<{ x: number; y: number; offsetX: number; offsetY: number } | null>(null);
  const uid = useId();
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; if (blob.current) URL.revokeObjectURL(blob.current); };
  }, []);
  useEffect(() => { if (crop) cropTitle.current?.focus(); }, [crop]);
  useEffect(() => { onPendingChange?.(busy); }, [busy, onPendingChange]);
  useEffect(() => () => { onPendingChange?.(false); }, [onPendingChange]);

  function clearCrop() {
    setCrop(null);
    if (blob.current) URL.revokeObjectURL(blob.current);
    blob.current = null;
    requestAnimationFrame(() => uploadButton.current?.focus());
  }
  async function upload(file?: File) {
    if (!file || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    let url: string | null = null;
    try {
      await inspectUpload(file);
      url = URL.createObjectURL(file);
      const img = new Image(); img.src = url;
      await img.decode();
      if (!mounted.current) { URL.revokeObjectURL(url); return; }
      if (img.naturalWidth > 8192 || img.naturalHeight > 8192 || img.naturalWidth * img.naturalHeight > 24_000_000) throw new Error("That image is too large. Try a smaller copy.");
      if (blob.current) URL.revokeObjectURL(blob.current);
      blob.current = url;
      setZoom(1); setX(50); setY(50);
      setCrop({ url, width: img.naturalWidth, height: img.naturalHeight });
    } catch (cause) {
      if (url) URL.revokeObjectURL(url);
      setError(cause instanceof Error && !(cause instanceof DOMException) ? cause.message : "We couldn’t open that image. Try another JPG, PNG, or WebP.");
    } finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function acceptCrop() {
    if (!crop || lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      const url = await exportCrop(crop, zoom, x, y);
      if (!mounted.current) return;
      const avatar = { id: "custom", url };
      setDraft(avatar); setCustom(avatar); clearCrop();
    } catch { setError("We couldn’t crop that image. Try adjusting it again."); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  async function save() {
    if (lock.current) return;
    lock.current = true; setBusy(true); setError("");
    try {
      // An unchanged saved custom image is already persisted. Never refetch it.
      if (saveDraft) { const saved = await saveDraft(draft); if (mounted.current) onSaved(saved); return; }
      if (draft.id === initialAvatar.id && draft.url === initialAvatar.url) { onSaved(draft); return; }
      const response = await fetch("/browser-api/account/avatar", {
        method: "PUT", credentials: "same-origin", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft.url.startsWith("data:") ? { image_data: draft.url } : { preset: draft.id }),
      });
      if (!response.ok) throw new Error(response.status === 401 ? "Sign in again to save your profile picture." : "We couldn’t save your picture. Your selection is still here. Try again.");
      const result = await response.json();
      if (!result.avatar || typeof result.avatar.id !== "string" || typeof result.avatar.url !== "string") throw new Error("We couldn’t confirm the save. Please try again.");
      if (mounted.current) onSaved(result.avatar);
    } catch (cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : "We couldn’t save your picture. Please try again."); }
    finally { lock.current = false; if (mounted.current) setBusy(false); }
  }
  function move(event: PointerEvent<HTMLDivElement>) {
    if (!drag.current || !crop || !preview.current || busy) return;
    const size = preview.current.clientWidth;
    const bounds = cropGeometry(crop, zoom, x, y, size);
    const clamp = (value: number) => Math.max(0, Math.min(100, value));
    if (bounds.width > size) setX(clamp(drag.current.offsetX - (event.clientX - drag.current.x) * 100 / (bounds.width - size)));
    if (bounds.height > size) setY(clamp(drag.current.offsetY - (event.clientY - drag.current.y) * 100 / (bounds.height - size)));
  }
  const bounds = crop ? cropGeometry(crop, zoom, x, y, 100) : null;
  return <section className="character-picker" aria-busy={busy} aria-labelledby={`${uid}-title`}>
    <style>{styles}</style>
    {crop && bounds ? <>
      <h2 ref={cropTitle} tabIndex={-1} id={`${uid}-title`}>Make it yours</h2>
      <p>Drag your image to frame it just right.</p>
      <div ref={preview} className="character-crop" aria-label="Circular crop preview. Use the sliders below to adjust your image."
        onPointerDown={event => { if (busy) return; event.currentTarget.setPointerCapture(event.pointerId); drag.current = { x: event.clientX, y: event.clientY, offsetX: x, offsetY: y }; }}
        onPointerMove={move} onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }} onLostPointerCapture={() => { drag.current = null; }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={crop.url} alt="Your image crop" draggable={false} style={{ position: "absolute", width: `${bounds.width}%`, height: `${bounds.height}%`, maxWidth: "none", left: `${bounds.left}%`, top: `${bounds.top}%` }} />
      </div>
      <label className="character-slider">Zoom <input type="range" min="1" max="3" step="0.01" value={zoom} disabled={busy} onChange={event => setZoom(Number(event.target.value))} /></label>
      <details className="character-adjust"><summary>Fine-tune position</summary>
        <label className="character-slider">Horizontal <input type="range" min="0" max="100" value={x} disabled={busy} onChange={event => setX(Number(event.target.value))} /></label>
        <label className="character-slider">Vertical <input type="range" min="0" max="100" value={y} disabled={busy} onChange={event => setY(Number(event.target.value))} /></label>
      </details>
      <div className="character-actions"><button className="character-primary" disabled={busy} onClick={acceptCrop}>{busy ? "Preparing…" : "Use this crop"}</button><button className="character-secondary" disabled={busy} onClick={() => { setError(""); clearCrop(); }}>Cancel crop</button></div>
    </> : <>
      <h2 id={`${uid}-title`} style={compact ? { fontSize: 16, textAlign: "left", marginBottom: 20, letterSpacing: 0 } : undefined}>Choose your avatar</h2>
      {!compact && <p>Pick an avatar or upload your own picture.</p>}
      {!compact && <div className="character-large">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={draft.url} alt={`${names[draft.id] || "Your profile picture"} preview`} />
      </div>}
      <div className="character-options" role="group" aria-label="Choose an avatar">
        {presets.map(id => <button key={id} className="character-option" aria-pressed={draft.id === id} disabled={busy} onClick={() => { setDraft({ id, url: `/characters/${id}.webp` }); setError(""); }}>
          <span className="character-tile">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/characters/${id}.webp`} alt="" />{draft.id === id && <span className="character-check" aria-hidden="true">✓</span>}
          </span><span>{names[id]}</span>
        </button>)}
        {custom && <button className="character-option" aria-pressed={draft.id === custom.id && draft.url === custom.url} disabled={busy} onClick={() => { setDraft(custom); setError(""); }}><span className="character-tile">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={custom.url} alt="" />{draft.id === custom.id && <span className="character-check" aria-hidden="true">✓</span>}</span><span>Your image</span></button>}
        <button ref={uploadButton} className="character-option" disabled={busy} onClick={() => fileInput.current?.click()}><span className="character-tile character-upload" aria-hidden="true">+</span><span>Upload image</span></button>
      </div>
      <input ref={fileInput} type="file" accept="image/jpeg,image/png,image/webp" aria-label="Upload a profile picture" hidden onChange={event => { const file = event.target.files?.[0]; event.target.value = ""; void upload(file); }} />
      <p className="character-hint">JPG, PNG, or WebP. Up to 2 MB.</p>
      <div className="character-actions"><button className="character-primary" disabled={busy} onClick={save}>{busy ? "Please wait…" : saveLabel ?? "Save"}</button>{onSkip && <button className="character-secondary" disabled={busy} onClick={onSkip}>Skip for now</button>}</div>
    </>}
    {error && <p className="character-error" role="alert">{error}</p>}
  </section>;
}

const styles = `
.character-picker{width:100%;max-width:600px;margin:auto;color:#172b4d;text-align:center;font-family:inherit;box-sizing:border-box}
.character-picker *{box-sizing:border-box}.character-picker h2{font-size:clamp(24px,5vw,30px);font-weight:750;line-height:1.2;letter-spacing:-.035em;margin:0 0 10px}.character-picker p{color:#65748b;font-size:14px;line-height:1.5;margin:0 0 20px}
.character-large{width:160px;height:160px;margin:24px auto 28px;padding:6px;border:2px solid #b5d5ff;border-radius:50%;box-shadow:0 8px 30px #2867af12;background:#fff}.character-large img,.character-tile img{width:100%;height:100%;object-fit:cover;border-radius:50%}
.character-options{display:grid;grid-template-columns:repeat(auto-fit,minmax(74px,1fr));gap:12px;max-width:520px;margin:0 auto}.character-option{border:0;background:transparent;padding:3px;color:#506078;font:inherit;font-size:12px;display:flex;align-items:center;flex-direction:column;gap:8px;cursor:pointer;min-width:0}.character-tile{position:relative;display:block;width:100%;max-width:82px;aspect-ratio:1;border:2px solid transparent;border-radius:50%;padding:3px;transition:border-color .15s,background .15s}.character-option[aria-pressed=true]{color:#1763b5;font-weight:650}.character-option[aria-pressed=true] .character-tile{border-color:#2474c9;background:#eaf3ff}.character-option:hover .character-tile{background:#eaf3ff}.character-check{position:absolute;right:0;bottom:0;background:#2474c9;border:2px solid white;border-radius:50%;color:white;width:22px;height:22px;display:grid;place-items:center;font-size:12px}.character-upload{border:1.5px dashed #a2b6cd;display:grid;place-items:center;font-size:32px;font-weight:300;color:#5280ad;background:#f7faff}.character-picker .character-hint{font-size:12px;margin:18px 0 24px}
.character-actions{display:flex;flex-direction:column;gap:8px;margin:24px auto 0;max-width:340px}.character-primary,.character-secondary{min-height:46px;border-radius:12px;padding:12px 20px;font:inherit;font-size:14px;font-weight:650;cursor:pointer}.character-primary{color:white;background:#176bc1;border:1px solid #176bc1;box-shadow:0 3px 7px #176bc120}.character-primary:hover{background:#125aab}.character-secondary{color:#52657d;border:1px solid transparent;background:transparent}.character-secondary:hover{background:#f0f5fb}.character-picker button:disabled{opacity:.55;cursor:wait}.character-picker :focus-visible{outline:3px solid #2d81df;outline-offset:4px}.character-picker .character-error{color:#a82d39;background:#fff1f1;border-radius:10px;padding:12px;margin:16px 0 0;text-align:left}
.character-crop{width:min(260px,100%);aspect-ratio:1;border-radius:50%;overflow:hidden;position:relative;margin:22px auto;background:#eef3fa;touch-action:none;cursor:grab;box-shadow:0 0 0 3px #b5d5ff}.character-crop:active{cursor:grabbing}.character-slider{display:flex;align-items:center;gap:16px;max-width:340px;margin:18px auto;font-size:13px;text-align:left}.character-slider input{min-width:0;flex:1;accent-color:#176bc1;height:28px}.character-adjust{max-width:340px;margin:auto;text-align:left;color:#52657d;font-size:13px}.character-adjust summary{cursor:pointer;min-height:32px;padding:6px 0}
@media(max-width:380px){.character-options{grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 8px}.character-large{width:136px;height:136px;margin:18px auto}.character-picker h2{font-size:24px}}
`;
