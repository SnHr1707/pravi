import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { api, postForm } from "../lib/api";
import { FIELD_ROLES, type AssetRow, type Flag, type Work } from "../lib/types";
import { STATUS_LABEL, WORK_TYPES, fdate } from "../lib/format";
import { Alert, Badge, FlagCard, useToast } from "../components/ui";
import { Can } from "../components/StaffLayout";

const DT: Record<string, string> = { sanction: "Approval / sanction order", tender: "Tender notice", award: "Work order (contract given)", completion: "Completion certificate", other: "Other" };
const SAMPLE_NOTE: Record<string, string> = {
  "1_": "A paid special-repair tender on a road still under the builder's liability → red flag",
  "2_": "The work order for that tender",
  "3_": "Completion certificate → starts a 36-month liability clock",
  "4_": "A legitimate resurfacing tender on an old road → no flag",
  N1: "New road, step 1: approval — creates the road and an Approved work",
  N2: "Step 2: tender notice — work moves to Tender out",
  N3: "Step 3: work order — contract given to Shreeji Infrastructure",
  N4: "Step 4: completion certificate — 36-month guarantee starts",
  N5: "Later: a paid repair tender on the new road → alert, contractor must fix free",
};
const FIELDS: [string, string, string][] = [
  ["road_name", "Road name", "text"], ["road_code", "Road code", "text"], ["taluka", "Taluka", "text"],
  ["start_km", "From km", "number"], ["end_km", "To km", "number"], ["work_type", "Work type", "select"],
  ["estimated_cost", "Estimated cost (₹)", "number"], ["awarded_cost", "Contract value (₹)", "number"], ["contractor", "Contractor / agency", "text"],
  ["completion_period_days", "Time limit (days)", "number"], ["liability_months", "Defects liability (months)", "number"], ["scheme", "Scheme / package", "text"],
  ["tender_date", "Tender date", "date"], ["award_date", "Award / work order date", "date"], ["completion_date", "Completion date", "date"],
  ["sanction_no", "Approval (A.A.) number", "text"], ["sanction_date", "Approval date", "date"],
];

interface Preview { effect: string; existing_work_id: number | null; liability_warning: { message: string } | null }
interface Doc {
  id: number; doc_type: string; filename: string; method: string; confidence: number; status: string;
  fields: Record<string, any>; asset: { id: number } | null; text_preview: string; preview: Preview | null;
}
interface DocRow { id: number; doc_type: string; filename: string; method: string; status: string; uploaded_by: string; created_at: string; has_file: boolean }

export default function Documents() {
  const [doc, setDoc] = useState<Doc | null>(null);
  const [saved, setSaved] = useState(false);
  const stage = !doc ? 1 : saved ? 3 : 2;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [url, setUrl] = useState("");
  const [drag, setDrag] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const docs = useQuery({ queryKey: ["documents"], queryFn: () => api<DocRow[]>("/api/documents") });
  const samples = useQuery({ queryKey: ["samples"], queryFn: () => api<{ name: string; url: string }[]>("/api/samples") });
  const llm = useQuery({ queryKey: ["llm"], queryFn: () => api<{ provider: string; model: string }>("/api/llm/status") });

  const ingest = async (p: Promise<Doc>) => {
    setBusy(true); setErr("");
    try { setSaved(false); setDoc(await p); } catch (e: any) { setErr(e.message); } finally { setBusy(false); qc.invalidateQueries({ queryKey: ["documents"] }); }
  };
  const upload = (f: File) => { const fd = new FormData(); fd.append("file", f); ingest(postForm<Doc>("/api/documents", fd)); };
  const trySample = async (s: { name: string; url: string }) => {
    const blob = await (await fetch(s.url)).blob();
    upload(new File([blob], s.name, { type: "application/pdf" }));
  };

  return (
    <>
      <div className="page-head">
        <div><h1>Upload documents</h1>
          <p>Upload a tender notice, work order or completion certificate. Pravi reads it and updates the road or building it is about.</p></div>
        <Badge>{llm.data ? (llm.data.provider === "none" ? "Reader: rules (no LLM configured)" : `Reader: rules + ${llm.data.model}`) : "…"}</Badge>
      </div>
      <div className="wiz">
        {["Upload a PDF", "Check the details", "Saved to the asset"].map((t, i) => (
          <div key={t} className={stage === i + 1 ? "on" : stage > i + 1 ? "ok" : ""}>{i > 0 && <span className="sep" />}<b>{stage > i + 1 ? "✓" : i + 1}</b>{t}</div>
        ))}
      </div>
      <div className="grid g-main">
        <div>
          <Can roles={FIELD_ROLES}>
            <div className="card">
              <div className={`dropzone ${drag ? "drag" : ""}`} onClick={() => fileRef.current?.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
                onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) upload(f); }}>
                <FileUp size={30} className="mx-auto" color="var(--brand-2)" />
                <b>Drop a PDF here or click to choose</b>
                <div className="small muted">Tender / NIT · Work order / Letter of acceptance · Completion certificate</div>
                <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
              </div>
              <form className="flex gap-2.5 mt-2.5" onSubmit={(e) => { e.preventDefault(); ingest(api<Doc>("/api/documents/from-url", { json: { url } })); }}>
                <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="…or paste a link to a public tender PDF (nprocure / R&B website)" />
                <button>Import</button>
              </form>
              {busy && <Alert tone="blue">Reading document…</Alert>}
              {err && <Alert tone="red">{err}</Alert>}
            </div>
          </Can>
          {doc && <Review key={doc.id} doc={doc} onDone={() => { setSaved(true); qc.invalidateQueries(); }} onReject={() => { setDoc(null); qc.invalidateQueries(); }} />}
        </div>
        <div>
          <Can roles={FIELD_ROLES}>
            <div className="card">
              <h2>Practice with sample documents</h2>
              <p className="small muted">Made-up PDFs in the real Gujarat R&amp;B format. Try them in order to see a road move through its life.</p>
              {samples.data?.map((s) => (
                <div className="li-row" key={s.name}>
                  <div className="flex-1"><a href={s.url} target="_blank">{s.name}</a><div className="small muted">{SAMPLE_NOTE[s.name.slice(0, 2)]}</div></div>
                  <button className="btn-sm" onClick={() => trySample(s)}>Try</button>
                </div>
              ))}
            </div>
          </Can>
          <div className="card">
            <h2>Document register</h2>
            {docs.data?.slice(0, 30).map((d) => (
              <div className="li-row" key={d.id}>
                <div className="flex-1">
                  <b>{DT[d.doc_type] || d.doc_type}</b> · {d.has_file ? <a href={`/api/documents/${d.id}/file`} target="_blank">{d.filename}</a> : d.filename}
                  <div className="small muted">{d.uploaded_by} · {fdate(d.created_at)} · {d.method}</div>
                </div>
                {d.status === "review"
                  ? <button className="btn-sm" onClick={async () => setDoc(await api<Doc>(`/api/documents/${d.id}`))}>Review</button>
                  : <Badge tone={d.status === "confirmed" ? "green" : ""}>{d.status}</Badge>}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}

function Review({ doc, onDone, onReject }: { doc: Doc; onDone: () => void; onReject: () => void }) {
  const assetsQ = useQuery({ queryKey: ["assets"], queryFn: () => api<AssetRow[]>("/api/assets") });
  const assets = (assetsQ.data || []).slice().sort((a, b) => a.code.localeCompare(b.code));
  const [fields, setFields] = useState<Record<string, any>>({ ...doc.fields });
  // no match in the inventory -> default to creating a new asset from this document
  const [assetId, setAssetId] = useState<string>(doc.asset ? String(doc.asset.id) : doc.preview?.existing_work_id ? "" : "new");
  const [preview, setPreview] = useState<Preview | null>(doc.preview);
  const [result, setResult] = useState<{ work: Work; created: boolean; flags: Flag[] } | null>(null);
  const [err, setErr] = useState("");
  const toast = useToast();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => ref.current?.scrollIntoView({ behavior: "smooth" }), []);

  // live preview of what confirming will do (debounced)
  useEffect(() => {
    const t = window.setTimeout(async () => {
      try {
        const r = await api<{ preview: Preview }>(`/api/documents/${doc.id}/preview`, { json: { fields, asset_id: assetId || null } });
        setPreview(r.preview);
      } catch { /* ignore */ }
    }, 400);
    return () => window.clearTimeout(t);
  }, [fields, assetId, doc.id]);

  const set = (k: string, v: any) => setFields((f) => ({ ...f, [k]: v }));
  const confirm = async (e: React.FormEvent) => {
    e.preventDefault(); setErr("");
    try {
      setResult(await api(`/api/documents/${doc.id}/confirm`, { json: { fields, asset_id: assetId || null } }));
      onDone();
    } catch (x: any) { setErr(x.message); }
  };
  const reject = async () => { await api(`/api/documents/${doc.id}/reject`, { method: "POST" }); toast("Document rejected"); onReject(); };
  const [showAll, setShowAll] = useState(false);
  const KEY: Record<string, string[]> = {
    sanction: ["road_name", "start_km", "end_km", "work_type", "estimated_cost", "sanction_no", "sanction_date"],
    tender: ["road_name", "start_km", "end_km", "work_type", "estimated_cost", "liability_months", "tender_date"],
    award: ["contractor", "awarded_cost", "completion_period_days", "award_date"],
    completion: ["contractor", "completion_date", "liability_months"],
  };
  const keyFields = KEY[fields.doc_type as string] || FIELDS.map((f) => f[0]);
  const visible = showAll ? FIELDS : FIELDS.filter(([k]) => keyFields.includes(k));

  if (result) return (
    <div className="card" ref={ref}>
      <h2>Saved ✓</h2>
      <p>{result.created ? "New work created" : "Work updated"}: <b>{result.work.title}</b> — now <Badge tone="blue">{STATUS_LABEL[result.work.status]}</Badge>
        {result.work.liability_end && <><br />Defects liability until <b>{fdate(result.work.liability_end)}</b></>}</p>
      {result.flags.map((f) => <FlagCard key={f.key} f={f} showAsset={false} />)}
      <Link className="btn btn-primary" to={`/app/assets/${result.work.asset_id}`}>Open asset timeline →</Link>
    </div>
  );
  const val = (k: string) => (fields[k] ?? "") as string;
  return (
    <div className="card" ref={ref}>
      <div className="card-head">
        <h2 className="m-0">Check what Pravi read</h2>
        <div className="flex gap-1">
          <Badge tone={doc.method === "llm" ? "blue" : ""}>read by: {doc.method === "llm" ? "LLM + rules" : "rules"}</Badge>
          <Badge tone={doc.confidence >= 0.8 ? "green" : doc.confidence >= 0.5 ? "amber" : "red"}>completeness {Math.round(doc.confidence * 100)}%</Badge>
        </div>
      </div>
      <div className="hint">From <b>{doc.filename}</b>. Correct anything that looks wrong, then press <b>Save</b>. Nothing changes until you save.</div>
      <form onSubmit={confirm}>
        <div className="row">
          <div><label>Document type</label>
            <select value={val("doc_type")} onChange={(e) => set("doc_type", e.target.value)}>
              {Object.entries(DT).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></div>
          <div><label>Tender ID</label><input value={val("tender_id")} onChange={(e) => set("tender_id", e.target.value)} /></div>
        </div>
        <label>Name of work</label><textarea value={val("title")} onChange={(e) => set("title", e.target.value)} />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-x-2.5">
          {visible.map(([k, label, type]) => (
            <div key={k}><label>{label}</label>
              {type === "select"
                ? <select value={val(k)} onChange={(e) => set(k, e.target.value)}><option value="">—</option>
                    {Object.entries(WORK_TYPES).map(([wk, wl]) => <option key={wk} value={wk}>{wl}</option>)}</select>
                : <input type={type} step={type === "number" ? "any" : undefined} value={val(k)} onChange={(e) => set(k, e.target.value)} />}
            </div>
          ))}
        </div>
        <button type="button" className="btn-sm mt-2" onClick={() => setShowAll(!showAll)}>{showAll ? "Show fewer fields" : "Show all fields"}</button>
        <label>Which road or building is this about?</label>
        <select value={assetId} onChange={(e) => setAssetId(e.target.value)}>
          <option value="">{doc.preview?.existing_work_id ? "— same asset as the earlier document —" : "— pick the asset —"}</option>
          <option value="new">+ Create new asset from this document</option>
          {assets.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}
        </select>
        {assetId === "new" && <p className="small muted">Not in the inventory yet — Pravi will register it (road name, km, taluka from the document) and place it on the map at the taluka. Later documents with the same tender ID move it along its lifecycle.</p>}
        {preview && <Alert tone="blue"><b>On confirm:</b> {preview.effect}</Alert>}
        {preview?.liability_warning && <Alert tone="red"><b>⚠ Liability check:</b> {preview.liability_warning.message} Paying for this work would duplicate a free repair.</Alert>}
        {err && <Alert tone="red">{err}</Alert>}
        <details className="mt-2.5"><summary className="small muted cursor-pointer">Show extracted text</summary>
          <pre className="small whitespace-pre-wrap rounded-lg p-2.5 max-h-64 overflow-auto" style={{ background: "#f7f8fa" }}>{doc.text_preview}</pre></details>
        <div className="actions">
          <a className="btn" href={`/api/documents/${doc.id}/file`} target="_blank">Open PDF</a>
          <button type="button" className="btn-danger" onClick={reject}>Reject</button>
          <button className="btn-primary">Save</button>
        </div>
      </form>
    </div>
  );
}
