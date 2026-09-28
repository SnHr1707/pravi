import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CircleMarker, Popup } from "react-leaflet";
import { Plus } from "lucide-react";
import { api, postForm } from "../lib/api";
import { compressImage } from "../lib/image";
import { FIELD_ROLES, type AssetType, type Complaint, type Flag, type Liability, type Permit, type Priority, type Work } from "../lib/types";
import { BAND_COLOR, STATUS_LABEL, TYPE_LABEL, daysAgo, fdate, fdt, inr } from "../lib/format";
import { AssetShape, BaseMap, FitBounds } from "../components/AssetMap";
import { Badge, BandBadge, ComplaintStatus, ErrorBox, FlagCard, Loading, Modal, ScoreBox, useToast } from "../components/ui";
import { Can } from "../components/StaffLayout";

interface Detail {
  asset: { id: number; code: string; type: AssetType; name: string; category: string; road_code: string | null; road_name: string | null;
    start_km: number | null; end_km: number | null; chainage_km: number | null; lat: number | null; lng: number | null; taluka: string | null;
    attrs: Record<string, any>; year_built: number | null; division: string; geometry: [number, number][] | null;
    office?: { id: number; name: string; level: string; head: string }[] };
  permits: Permit[];
  priority: Priority; liability: Liability; flags: Flag[]; works: Work[]; complaints: Complaint[];
  inspections: { id: number; kind: string; date: string; condition: number | null; notes: string | null; inspector: string | null; photo_url: string | null; safety_class?: string | null }[];
  documents: { id: number; doc_type: string; filename: string; method: string; has_file: boolean; created_at: string }[];
  timeline: { type: string; message: string; actor: string; at: string }[];
}

const ET_COLOR: Record<string, string> = {
  work_proposed: "#94a3b8", work_sanctioned: "#6366f1", work_tendered: "#0ea5e9", work_awarded: "#0284c7", work_started: "#f59e0b",
  work_completed: "#16a34a", work_cancelled: "#64748b", complaint_reported: "#e8870e", complaint_merged: "#e8870e",
  complaint_verified: "#2563eb", complaint_assigned: "#7c3aed", complaint_fixed: "#16a34a", complaint_closed: "#15803d",
  complaint_reopened: "#dc2626", complaint_rejected: "#64748b", liability_check: "#1f5fbf", liability_warning: "#dc2626",
  inspection: "#0f766e", cleaning: "#0f766e", structural_audit: "#0f766e", registered: "#334155",
  dig_applied: "#a16207", dig_approved: "#a16207", dig_rejected: "#64748b", dig_restored: "#16a34a",
};
const FACTOR_LABEL: Record<string, string> = { condition: "Condition", criticality: "Criticality", complaints: "Complaints (90 d)", age: "Age since renewal", repeat: "Repeat repairs" };

export default function AssetDetail() {
  const { id } = useParams();
  const q = useQuery({ queryKey: ["asset", id], queryFn: () => api<Detail>(`/api/assets/${id}`) });
  const [inspOpen, setInspOpen] = useState(false);
  const [tab, setTab] = useState<string>("history");
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const { asset: a, priority: p, liability: li } = q.data;
  const d = q.data;
  const pts = a.geometry || (a.lat !== null ? [[a.lat, a.lng!] as [number, number]] : []);

  return (
    <>
      <div className="page-head">
        <div>
          <div className="small muted"><Link to="/app/assets">Roads & buildings</Link> / {a.code}</div>
          <h1>{a.name}</h1>
          <div className="flex gap-1 flex-wrap">
            <Badge tone="dark">{TYPE_LABEL[a.type]}</Badge>{a.taluka && <Badge>Taluka {a.taluka}</Badge>}
            {a.office && a.office.length > 0 && <Badge tone="blue" title={a.office.map((o) => o.name).join(" › ")}>Maintained by {a.office[a.office.length - 1].name}</Badge>}
            {p.inputs.safety_class && <Badge tone={["C1", "C2A"].includes(p.inputs.safety_class) ? "red" : p.inputs.safety_class === "C2B" ? "amber" : "green"}>Structural class {p.inputs.safety_class}</Badge>}
          </div>
        </div>
        <Can roles={FIELD_ROLES}>
          <div className="flex gap-2">
            <button onClick={() => setInspOpen(true)}><Plus size={15} />Log inspection</button>
            <Link className="btn btn-primary" to={`/app/works?propose=${a.id}`}>Propose repair / work</Link>
          </div>
        </Can>
      </div>

      <div className="grid g3">
        <div className="card">
          <h2>Who pays for repairs?</h2>
          <div className="rounded-xl px-4 py-3.5" style={li.under_liability ? { background: "var(--green-bg)", border: "1px solid #a8dfc1" } : { background: "#f4f5f7", border: "1px solid var(--line)" }}>
            {li.under_liability ? (
              <>
                <div className="small font-bold" style={{ color: "var(--green)" }}>UNDER GUARANTEE — CONTRACTOR PAYS</div>
                <div className="text-lg font-extrabold">{li.contractor}</div>
                <div>must repair any defect for free until <b>{fdate(li.until)}</b> ({li.days_left} days left).</div>
                <div className="small muted mt-1">Guarantee from: {li.work_title}{li.estimated ? " · completion date estimated" : ""} · Clause 17-A of the contract</div>
              </>
            ) : (
              <><div className="small muted font-bold">NO GUARANTEE</div><div className="text-lg font-extrabold">Department pays</div>
                <div className="muted">No contractor guarantee covers this asset today.</div></>
            )}
          </div>
          <div className="kv mt-3.5">
            {a.start_km !== null && <><div>Stretch</div><div>km {a.start_km} to {a.end_km}</div></>}
            {a.chainage_km !== null && <><div>Located at</div><div>km {a.chainage_km} of {a.road_code}</div></>}
            {a.year_built && <><div>Built</div><div>{a.year_built}</div></>}
            <div>Condition</div><div>{p.inputs.condition ? `${p.inputs.condition} out of 5` : "not inspected yet"}</div>
          </div>
        </div>

        <div className="card">
          <div className="card-head"><h2 className="m-0">What should we do?</h2></div>
          <div className="flex gap-3 items-center">
            <ScoreBox score={p.score} band={p.band} size={64} />
            <div><BandBadge band={p.band} /><div className="mt-1"><b>{p.action}</b></div>
              {p.urgent && <div className="small" style={{ color: "var(--red)" }}>{p.urgent_reason}</div>}</div>
          </div>
          <details className="mt-3">
            <summary className="small cursor-pointer" style={{ color: "var(--brand-2)", fontWeight: 600 }}>Why this score?</summary>
            <div className="mt-2">
              {Object.entries(p.factors).map(([k, v]) => (
                <div key={k} className="grid items-center gap-2 my-1.5 text-[13px]" style={{ gridTemplateColumns: "120px 1fr 90px" }}>
                  <span>{FACTOR_LABEL[k]}</span><div className="bar"><i style={{ width: `${Math.round(v * 100)}%` }} /></div>
                  <span className="small muted">{Math.round(v * 100)}% × {Math.round(p.weights[k] * 100)}%</span>
                </div>
              ))}
              <div className="small muted">{p.inputs.reports_90d} citizen reports in 90 days · {p.inputs.years_since_major_work ?? "?"} years since last renewal · {p.inputs.repairs_12m} repairs in the last year</div>
            </div>
          </details>
        </div>

        <div className="card">
          <h2>Location</h2>
          <BaseMap height={240} zoom={12}>
            <FitBounds points={pts} />
            <AssetShape a={a} color={BAND_COLOR[p.band]} weight={7} />
            {d.complaints.filter((c) => !["closed", "rejected"].includes(c.status)).map((c) => (
              <CircleMarker key={c.id} center={[c.lat, c.lng]} radius={6} pathOptions={{ color: "#fff", weight: 2, fillColor: "#e8870e", fillOpacity: 1 }}>
                <Popup>{c.ticket} · {c.issue_label}</Popup>
              </CircleMarker>
            ))}
          </BaseMap>
          {pts.length === 0 && <p className="small muted">Not placed on the map yet.</p>}
        </div>
      </div>

      {d.flags.length > 0 && <div className="card mt-4"><h2>Alerts</h2>{d.flags.map((f) => <FlagCard key={f.key} f={f} showAsset={false} />)}</div>}

      <div className="ptabs">
        {([["history", "History", d.timeline.length], ["works", "Works & contracts", d.works.length], ["complaints", "Complaints", d.complaints.length],
          ["inspections", "Inspections", d.inspections.length], ["documents", "Documents", d.documents.length],
          ...(a.type === "road_section" ? [["digging", "Road digging", d.permits.length] as const] : []), ["details", "Details", 0]] as const).map(([k, l, n]) => (
          <button key={k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}{n ? <span className="badge">{n}</span> : null}</button>
        ))}
      </div>

      <div className="card">
        {tab === "history" && (
          <>
            <p className="small muted mt-0">Everything that ever happened to this asset, newest first. Records are never edited or deleted.</p>
            <div className="timeline">
              {d.timeline.map((e, i) => (
                <div key={i} className="tl-item" style={{ ["--c" as any]: ET_COLOR[e.type] || "#94a3b8" }}>
                  <div>{e.message}</div><div className="when">{fdt(e.at)} · {e.actor}</div>
                </div>
              ))}
            </div>
          </>
        )}
        {tab === "works" && (d.works.length ? d.works.map((w) => (
          <div className="li-row" key={w.id}><div className="flex-1">
            <b>{w.title}</b> <Badge tone={w.status === "completed" ? "green" : "blue"}>{STATUS_LABEL[w.status]}</Badge>
            <div className="small muted">{w.tender_id ? `Tender ${w.tender_id} · ` : ""}{w.contractor ? `${w.contractor} · ` : ""}{inr(w.awarded_cost || w.estimated_cost)}{w.start_km !== null ? ` · km ${w.start_km}–${w.end_km}` : ""}</div>
            {w.liability_end && <div className="small">Guarantee: {w.liability_months} months, until {fdate(w.liability_end)}</div>}
          </div></div>
        )) : <p className="muted">No works recorded.</p>)}
        {tab === "complaints" && (d.complaints.length ? d.complaints.map((c) => (
          <div className="li-row" key={c.id}><div className="flex-1">
            <b>{c.issue_label}</b> <ComplaintStatus s={c.status} />
            <div className="small muted">{c.ticket} · {c.km !== null ? `km ${c.km} · ` : ""}{c.report_count} report(s) · {daysAgo(c.created_at)}</div>
          </div></div>
        )) : <p className="muted">No complaints.</p>)}
        {tab === "inspections" && (d.inspections.length ? (
          <table><thead><tr><th>Date</th><th>Type</th><th>Condition</th><th>Notes</th></tr></thead><tbody>
            {d.inspections.map((i) => (
              <tr key={i.id}><td className="whitespace-nowrap">{fdate(i.date)}</td><td>{i.kind.replace("_", " ")}{i.safety_class && <> · <b>{i.safety_class}</b></>}</td><td>{i.condition ? `${i.condition}/5` : "—"}</td>
                <td className="small">{i.notes} <span className="muted">{i.inspector}</span>{i.photo_url && <> <a href={i.photo_url} target="_blank">photo</a></>}</td></tr>
            ))}
          </tbody></table>
        ) : <p className="muted">No inspections yet.</p>)}
        {tab === "documents" && (d.documents.length ? d.documents.map((doc) => (
          <div className="li-row" key={doc.id}><div>
            {doc.doc_type} · {doc.has_file ? <a href={`/api/documents/${doc.id}/file`} target="_blank">{doc.filename}</a> : doc.filename}
            <span className="small muted"> · {fdate(doc.created_at)}</span>
          </div></div>
        )) : <p className="muted">No documents yet.</p>)}
        {tab === "digging" && (d.permits.length ? d.permits.map((pm) => (
          <div className="li-row" key={pm.id}><div className="flex-1">
            <b>{pm.agency}</b> — {pm.purpose} <Badge tone={pm.status === "restored" ? "green" : pm.status === "rejected" ? "" : pm.overdue_days ? "red" : "amber"}>{pm.status === "approved" && pm.overdue_days ? "Not restored" : pm.status}</Badge>
            <div className="small muted">Permit #{pm.id} · km {pm.start_km}–{pm.end_km} · {fdate(pm.from_date)} to {fdate(pm.to_date)}{pm.utility_liable_until ? ` · utility liable until ${fdate(pm.utility_liable_until)}` : ""}</div>
          </div></div>
        )) : <p className="muted">No utility has dug this road. <Link to="/app/digging">Road-digging permits →</Link></p>)}
        {tab === "details" && (
          <div className="kv">
            <div>Asset code</div><div>{a.code}</div>
            {a.road_code && <><div>Road</div><div>{a.road_code} · {a.road_name}</div></>}
            <div>Maintained by</div><div>{a.office && a.office.length ? a.office.slice(1).map((o) => o.name).join(" › ") : a.division}</div>
            {Object.entries(a.attrs || {}).map(([k, v]) => <Attr key={k} k={k} v={v} />)}
          </div>
        )}
      </div>
      {inspOpen && <InspectionModal assetId={a.id} code={a.code} type={a.type} onClose={() => setInspOpen(false)} />}
    </>
  );
}

const Attr = ({ k, v }: { k: string; v: any }) => <><div>{k.replace(/_/g, " ")}</div><div>{String(v)}</div></>;

function InspectionModal({ assetId, code, type, onClose }: { assetId: number; code: string; type: AssetType; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [kind, setKind] = useState("inspection");
  const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    if (!fd.get("condition")) fd.delete("condition");
    if (!fd.get("safety_class")) fd.delete("safety_class");
    const ph = fd.get("photo") as File | null;
    if (!ph || !ph.name) fd.delete("photo");
    else fd.set("photo", await compressImage(ph), "photo.jpg");
    setBusy(true); setErr("");
    try {
      await postForm(`/api/assets/${assetId}/inspections`, fd);
      toast("Inspection saved");
      qc.invalidateQueries();
      onClose();
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <Modal title={`Log inspection — ${code}`} onClose={onClose}>
      <form onSubmit={submit}>
        <div className="row">
          <div><label>Type</label><select name="kind" value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="inspection">Inspection</option>
            {type === "culvert" && <option value="cleaning">Pre-monsoon cleaning (desilting)</option>}
            {(type === "building" || type === "bridge") && <option value="structural_audit">Structural audit</option>}
          </select></div>
          <div><label>Condition (1 very poor – 5 good)</label><select name="condition"><option value="">—</option>{[5, 4, 3, 2, 1].map((n) => <option key={n}>{n}</option>)}</select></div>
        </div>
        {kind === "structural_audit" && <>
          <label>Safety class (from the audit report)</label>
          <select name="safety_class" defaultValue="">
            <option value="">— not classified —</option>
            <option value="C1">C1 — dangerous: close / evacuate now</option>
            <option value="C2A">C2A — major repairs, vacate while repairing</option>
            <option value="C2B">C2B — major repairs, can stay in use</option>
            <option value="C3">C3 — minor repairs</option>
          </select></>}
        <label>Notes</label><textarea name="notes" />
        <label>Photo{kind === "cleaning" ? " (required — proof the drain was cleaned)" : ""}</label><input type="file" name="photo" accept="image/*" capture="environment" required={kind === "cleaning"} />
        {err && <div className="alert alert-red">{err}</div>}
        <div className="actions"><button type="button" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={busy}>Save</button></div>
      </form>
    </Modal>
  );
}
