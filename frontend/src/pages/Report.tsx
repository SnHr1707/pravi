import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Marker, Polyline, useMapEvents } from "react-leaflet";
import { LocateFixed } from "lucide-react";
import { api, postForm } from "../lib/api";
import { compressImage } from "../lib/image";
import { ISSUE_ICONS, T, type Lang } from "../lib/i18n";
import { BaseMap, FitBounds } from "../components/AssetMap";
import { Alert } from "../components/ui";

type MapAsset = { geometry: [number, number][] | null };
type Result = { ticket: string; merged: boolean; asset: string; km: number | null; liable_contractor: string | null; liable_utility?: string | null; sla_hours?: number };

function ClickToPin({ onPick }: { onPick: (p: [number, number]) => void }) {
  useMapEvents({ click: (e) => onPick([e.latlng.lat, e.latlng.lng]) });
  return null;
}

function initialLang(): Lang {
  try { return (localStorage.getItem("pravi_lang") as Lang) || "en"; } catch { return "en"; }
}

export default function Report() {
  const [lang, setLang] = useState<Lang>(initialLang);
  const t = T[lang];
  const [pin, setPin] = useState<[number, number] | null>(null);
  const [issue, setIssue] = useState<string | null>(null);
  const [desc, setDesc] = useState("");
  const [contact, setContact] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Result | null>(null);
  const [focus, setFocus] = useState<[number, number][]>([]);

  const { data: assets = [] } = useQuery({ queryKey: ["public-map"], queryFn: () => api<MapAsset[]>("/api/public/map") });
  const roads = assets.filter((a) => a.geometry);
  const allPts = roads.flatMap((a) => a.geometry!) as [number, number][];

  const chooseLang = (l: Lang) => { setLang(l); try { localStorage.setItem("pravi_lang", l); } catch { /* ignore */ } };
  const locate = () => {
    setMsg(t.locating);
    navigator.geolocation.getCurrentPosition(
      (p) => { const q: [number, number] = [p.coords.latitude, p.coords.longitude]; setPin(q); setFocus([q]); setMsg(""); },
      () => setMsg(t.noloc), { enableHighAccuracy: true, timeout: 10000 });
  };
  const submit = async () => {
    setErr("");
    if (!pin) return setErr(t.needpin);
    if (!issue) return setErr(t.needissue);
    const fd = new FormData();
    fd.append("lat", String(pin[0])); fd.append("lng", String(pin[1])); fd.append("issue_type", issue);
    fd.append("description", desc); fd.append("contact", contact); fd.append("language", lang);
    if (photo) fd.append("photo", await compressImage(photo), "photo.jpg");
    setBusy(true);
    try { setDone(await postForm<Result>("/api/public/complaints", fd)); window.scrollTo(0, 0); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };

  return (
    <div className="min-h-screen" style={{ background: "#eef2f8" }} lang={lang}>
      <div className="max-w-xl mx-auto px-3.5 pt-3.5 pb-10">
        <div className="flex items-center justify-between mb-3">
          <Link to="/" className="flex items-center gap-2 font-extrabold" style={{ color: "var(--ink)" }}>
            <span className="w-7 h-7 rounded-md grid place-items-center text-white" style={{ background: "var(--accent)" }}>P</span>{t.brand}
          </Link>
          <div className="flex gap-1">
            {(["en", "gu", "hi"] as Lang[]).map((l) => (
              <button key={l} className={`btn-sm ${l === lang ? "btn-primary" : ""}`} onClick={() => chooseLang(l)}>{{ en: "EN", gu: "ગુ", hi: "हि" }[l]}</button>
            ))}
          </div>
        </div>

        {done ? (
          <div className="card text-center">
            <div className="text-5xl">✅</div>
            <h2>{t.thanks}</h2>
            <div className="text-3xl font-extrabold tracking-wide my-1.5" style={{ color: "var(--brand)" }}>{done.ticket}</div>
            <p className="muted">{done.asset}{done.km !== null ? ` · km ${done.km}` : ""}</p>
            {done.merged && <Alert tone="blue">{t.merged}</Alert>}
            {done.liable_contractor && <Alert tone="green">{t.liable(done.liable_contractor)}</Alert>}
            {done.liable_utility && <Alert tone="green">{t.utility(done.liable_utility)}</Alert>}
            {done.sla_hours && <p className="small">⏱ {done.sla_hours < 48 ? `${done.sla_hours} h` : `${done.sla_hours / 24} d`}</p>}
            <Link className="btn btn-primary w-full btn-lg" to={`/track?t=${done.ticket}`}>{t.track}</Link>
            <p><a href="/report">{t.another}</a></p>
          </div>
        ) : (
          <>
            <div className="card">
              <Step n={1} text={t.where} />
              <BaseMap height={300} scroll>
                {roads.map((a, i) => <Polyline key={i} positions={a.geometry!} pathOptions={{ color: "#274b8a", weight: 4, opacity: 0.55 }} />)}
                <FitBounds points={focus.length ? focus : allPts} />
                <ClickToPin onPick={(p) => { setPin(p); setMsg(""); }} />
                {pin && <Marker position={pin} />}
              </BaseMap>
              <div className="flex items-center gap-2.5 mt-2">
                <button className="btn-primary" onClick={locate}><LocateFixed size={16} />{t.useloc}</button>
                <span className="small muted">{msg || (pin ? t.pinned : t.tap)}</span>
              </div>
            </div>
            <div className="card">
              <Step n={2} text={t.what} />
              <div className="grid grid-cols-3 gap-2">
                {Object.keys(ISSUE_ICONS).map((k) => (
                  <button key={k} onClick={() => setIssue(k)}
                    className="rounded-xl bg-white py-3 px-1.5 text-[13px] font-semibold flex flex-col items-center"
                    style={{ border: `2px solid ${issue === k ? "var(--brand)" : "var(--line)"}`, background: issue === k ? "var(--blue-bg)" : "#fff" }}>
                    <span className="text-3xl mb-1">{ISSUE_ICONS[k]}</span>{t.issues[k]}
                  </button>
                ))}
              </div>
            </div>
            <div className="card">
              <Step n={3} text={t.details} />
              <label>{t.photo}</label>
              <input type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] || null)} />
              <label>{t.desc}</label>
              <textarea value={desc} maxLength={1000} onChange={(e) => setDesc(e.target.value)} />
              <label>{t.phone}</label>
              <input value={contact} inputMode="tel" maxLength={15} onChange={(e) => setContact(e.target.value)} />
            </div>
            {err && <Alert tone="red">{err}</Alert>}
            <button className="btn-accent w-full mt-3.5 py-4 text-[17px] rounded-xl" disabled={busy} onClick={submit}>{busy ? t.sending : t.submit}</button>
            <p className="small muted text-center">{t.nologin}</p>
          </>
        )}
      </div>
    </div>
  );
}

const Step = ({ n, text }: { n: number; text: string }) => (
  <div className="flex items-center gap-2 font-bold text-base mb-2">
    <span className="w-6 h-6 rounded-full grid place-items-center text-white text-[13px]" style={{ background: "var(--brand)" }}>{n}</span>{text}
  </div>
);
