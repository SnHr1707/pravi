import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "../lib/api";
import { FIELD_ROLES, SENIOR_ROLES, type AssetRow, type Permit } from "../lib/types";
import { fdate, inr } from "../lib/format";
import { Alert, Badge, ErrorBox, Loading, Modal, useToast } from "../components/ui";
import { Can, useMe } from "../components/StaffLayout";

const AGENCIES = ["Gujarat Gas Ltd", "GSPC", "MGVCL (electricity)", "Vadodara Municipal Corporation (water)", "Gujarat Water Supply Board", "BSNL", "Jio / Airtel (fibre)"];

function StatusBadge({ p }: { p: Permit }) {
  if (p.status === "approved" && p.overdue_days > 0) return <Badge tone="red">Not restored · {p.overdue_days} days late</Badge>;
  const m: Record<string, [string, string]> = { applied: ["Waiting for decision", "amber"], approved: ["Digging allowed", "blue"],
    restored: ["Restored", "green"], rejected: ["Rejected", ""] };
  return <Badge tone={m[p.status][1]}>{m[p.status][0]}</Badge>;
}

export default function Digging() {
  const q = useQuery({ queryKey: ["permits"], queryFn: () => api<Permit[]>("/api/permits") });
  const me = useMe().data;
  const qc = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState("");
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const senior = !!me && SENIOR_ROLES.includes(me.role);
  const act = async (p: Permit, action: string) => {
    setErr("");
    try { await api(`/api/permits/${p.id}/decide`, { json: { action } }); qc.invalidateQueries(); toast(action === "restored" ? "Marked restored" : `Permit ${action}d`); }
    catch (x: any) { setErr(`Permit #${p.id}: ${x.message}`); }
  };

  return (
    <>
      <div className="page-head">
        <div><h1>Road digging by utilities</h1>
          <p>Gas, water, power and cable companies must get permission before cutting a road, and must restore it. A road still in the
            first year of its builder's guarantee cannot be dug except in an emergency, and there is no digging in the monsoon.
            Damage at a dug spot is the utility's to fix for a year — not the road contractor's.</p></div>
        <Can roles={FIELD_ROLES}><button className="btn-primary" onClick={() => setOpen(true)}><Plus size={16} />New digging request</button></Can>
      </div>
      {err && <Alert tone="red">{err}</Alert>}
      {q.data.length === 0 && <div className="card muted">No digging requests yet.</div>}
      {q.data.map((p) => (
        <div className="ccard" key={p.id} style={{ gridTemplateColumns: "1fr auto" }}>
          <div className="min-w-0">
            <div className="flex gap-2 items-center flex-wrap"><b>{p.agency}</b> <StatusBadge p={p} />{p.emergency && <Badge tone="red">Emergency</Badge>}</div>
            <div className="small" style={{ color: "var(--ink-2)" }}>
              <Link to={`/app/assets/${p.asset_id}`}>{p.asset_name}</Link> · km {p.start_km}–{p.end_km} · {p.purpose || "utility work"}
            </div>
            <div className="small muted">Permit #{p.id} · digging {fdate(p.from_date)} to {fdate(p.to_date)} · restoration charge {inr(p.restoration_charge)}
              {p.utility_liable_until && <> · utility liable for defects until {fdate(p.utility_liable_until)}</>}</div>
            {p.decision_note && <div className="small mt-1">{p.decision_note}{p.decided_by ? ` — ${p.decided_by}` : ""}</div>}
          </div>
          <div className="flex flex-col gap-1.5" style={{ minWidth: 150 }}>
            {senior && p.status === "applied" && <>
              <button className="btn-primary btn-sm" onClick={() => act(p, "approve")}>Approve</button>
              <button className="btn-danger btn-sm" onClick={() => act(p, "reject")}>Reject</button></>}
            {senior && p.status === "approved" && <button className="btn-sm" onClick={() => act(p, "restored")}>Mark road restored</button>}
            {!senior && p.status === "applied" && <span className="small muted text-center">Executive Engineer decides</span>}
          </div>
        </div>
      ))}
      {open && <NewPermit onClose={() => setOpen(false)} />}
    </>
  );
}

function NewPermit({ onClose }: { onClose: () => void }) {
  const assetsQ = useQuery({ queryKey: ["assets"], queryFn: () => api<AssetRow[]>("/api/assets") });
  const qc = useQueryClient();
  const toast = useToast();
  const roads = (assetsQ.data || []).filter((a) => a.type === "road_section").sort((a, b) => a.code.localeCompare(b.code));
  const today = new Date();
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const [f, setF] = useState<Record<string, any>>({ agency: AGENCIES[0], from_date: iso(new Date(today.getTime() + 7 * 864e5)),
    to_date: iso(new Date(today.getTime() + 14 * 864e5)), purpose: "", emergency: false });
  const [check, setCheck] = useState<{ blocked: string | null; notes: string[]; restoration_charge: number } | null>(null);
  const [err, setErr] = useState("");
  const aid = f.asset_id || (roads[0] && String(roads[0].id));
  const sel = roads.find((r) => String(r.id) === aid);
  const set = (k: string, v: any) => { setF({ ...f, [k]: v }); setCheck(null); };
  const body = () => ({ ...f, asset_id: aid });
  const run = async (save: boolean) => {
    setErr("");
    try {
      if (!save) setCheck(await api("/api/permits/check", { json: body() }));
      else { await api("/api/permits", { json: body() }); qc.invalidateQueries(); toast("Digging request saved"); onClose(); }
    } catch (x: any) { setErr(x.message); }
  };
  return (
    <Modal title="New road-digging request" onClose={onClose}>
      <label>Road section</label>
      <select value={aid || ""} onChange={(e) => set("asset_id", e.target.value)}>
        {roads.map((r) => <option key={r.id} value={r.id}>{r.code} · {r.name}</option>)}
      </select>
      <div className="row">
        <div><label>From km</label><input type="number" step="0.01" placeholder={sel ? String(sel.start_km) : ""} value={f.start_km ?? ""} onChange={(e) => set("start_km", e.target.value)} /></div>
        <div><label>To km</label><input type="number" step="0.01" value={f.end_km ?? ""} onChange={(e) => set("end_km", e.target.value)} /></div>
      </div>
      <label>Agency that will dig</label>
      <input list="agencies" value={f.agency} onChange={(e) => set("agency", e.target.value)} />
      <datalist id="agencies">{AGENCIES.map((a) => <option key={a} value={a} />)}</datalist>
      <label>Purpose</label><input value={f.purpose} onChange={(e) => set("purpose", e.target.value)} placeholder="e.g. gas pipeline, water main crossing" />
      <div className="row">
        <div><label>Digging from</label><input type="date" value={f.from_date} onChange={(e) => set("from_date", e.target.value)} /></div>
        <div><label>to</label><input type="date" value={f.to_date} onChange={(e) => set("to_date", e.target.value)} /></div>
      </div>
      <label className="flex gap-2 items-center font-medium"><input type="checkbox" className="w-auto" checked={f.emergency} onChange={(e) => set("emergency", e.target.checked)} /> Emergency (leak, burst, cable fault)</label>
      {check && (check.blocked
        ? <Alert tone="red"><b>Cannot be allowed:</b> {check.blocked}</Alert>
        : <Alert tone="green"><b>Can be allowed.</b> Restoration charge {inr(check.restoration_charge)}.{check.notes.map((n, i) => <div key={i} className="mt-1">{n}</div>)}</Alert>)}
      {err && <Alert tone="red">{err}</Alert>}
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button onClick={() => run(false)}>Check the rules</button>
        <button className="btn-primary" onClick={() => run(true)}>Save request</button>
      </div>
    </Modal>
  );
}
