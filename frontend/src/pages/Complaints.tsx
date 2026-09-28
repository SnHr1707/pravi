import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Camera, ExternalLink } from "lucide-react";
import { api, postForm } from "../lib/api";
import { compressImage } from "../lib/image";
import { FIELD_ROLES, type Complaint, type Sla } from "../lib/types";
import { daysAgo, fdate } from "../lib/format";
import { Alert, Badge, ComplaintStatus, ErrorBox, Loading, Modal, useToast } from "../components/ui";
import { useMe } from "../components/StaffLayout";
import { ISSUE_ICON } from "../lib/labels";

const TABS: [string, string, (c: Complaint) => boolean][] = [
  ["todo", "To do", (c) => ["open", "verified", "assigned"].includes(c.status)],
  ["late", "Past deadline", (c) => c.sla?.state === "overdue"],
  ["waiting", "Waiting for citizen", (c) => c.status === "fixed"],
  ["done", "Done", (c) => ["closed", "rejected"].includes(c.status)],
];
const STEPS = ["open", "verified", "assigned", "fixed", "closed"];
const STEP_TEXT = ["Reported", "Checked", "Repair given", "Repaired", "Closed"];
const NEXT: Record<string, ["verify" | "assign" | "fix", string]> = {
  open: ["verify", "Check on site"], verified: ["assign", "Assign repair"], assigned: ["fix", "Mark as repaired"],
};

function dur(h: number) {
  const a = Math.abs(h);
  return a < 48 ? `${Math.round(a)} h` : `${Math.round(a / 24)} days`;
}

export function SlaChip({ sla }: { sla?: Sla }) {
  if (!sla || sla.state === "na") return null;
  const limit = sla.hours < 48 ? `${sla.hours} h` : `${sla.hours / 24} days`;
  if (sla.state === "on_time") return <span className="sla ok" title={`Deadline: ${limit} from the report`}>⏱ {dur(sla.hours_left || 0)} left to repair</span>;
  if (sla.state === "overdue") return (
    <span className="sla late" title={`Deadline was ${limit} from the report`}>
      ⏱ {dur(sla.hours_left || 0)} late{sla.escalated_label ? ` · escalated to ${sla.escalated_label}` : ""}
    </span>);
  if (sla.state === "met") return <span className="sla ok">Repaired within {limit}</span>;
  return <span className="sla late">Repaired late (deadline {limit})</span>;
}

export default function Complaints() {
  const q = useQuery({ queryKey: ["complaints"], queryFn: () => api<Complaint[]>("/api/complaints") });
  const me = useMe().data;
  const [sp] = useSearchParams();
  const [tab, setTab] = useState(sp.get("tab") || "todo");
  const [search, setSearch] = useState("");
  const [action, setAction] = useState<{ kind: "verify" | "assign" | "fix"; c: Complaint } | null>(null);
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const all = q.data;
  const filter = TABS.find((t) => t[0] === tab)![2];
  const field = !!me && FIELD_ROLES.includes(me.role);
  const list = all.filter(filter).filter((c) => !search || (c.ticket + (c.asset_name || "") + c.issue_label).toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => (b.sla?.escalation_rank || 0) - (a.sla?.escalation_rank || 0));

  return (
    <>
      <div className="page-head">
        <div><h1>Complaints from citizens</h1>
          <p>Each complaint shows its next step and its repair deadline (potholes 48 h, 24 h in the monsoon). Late complaints move up to the Executive, then Superintending, then Chief Engineer.</p></div>
        <a className="btn" href="/report" target="_blank">Open citizen app <ExternalLink size={14} /></a>
      </div>
      <div className="flex gap-3 flex-wrap items-center mb-3">
        <div className="tabs m-0 flex-1">
          {TABS.map(([k, l, f]) => <button key={k} className={k === tab ? "on" : ""} onClick={() => setTab(k)}>{l} ({all.filter(f).length})</button>)}
        </div>
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search ticket or road…" style={{ maxWidth: 260 }} />
      </div>
      {list.length === 0 && <div className="card muted">Nothing here.</div>}
      {list.map((c) => {
        const idx = c.status === "rejected" ? -1 : STEPS.indexOf(c.status);
        const next = NEXT[c.status];
        return (
          <div className="ccard" key={c.id}>
            <div className="ic">{ISSUE_ICON[c.issue_type] || "✏️"}</div>
            <div className="min-w-0">
              <div className="flex gap-2 items-center flex-wrap">
                <b>{c.issue_label}</b> <ComplaintStatus s={c.status} />
                {c.report_count > 1 && <Badge tone="amber">{c.report_count} people reported</Badge>}
                <SlaChip sla={c.sla} />
              </div>
              <div className="small" style={{ color: "var(--ink-2)" }}>
                <Link to={`/app/assets/${c.asset_id}`}>{c.asset_name}</Link>{c.km !== null ? ` · km ${c.km}` : ""} · {daysAgo(c.created_at)} · <span className="mono">{c.ticket}</span>{c.office ? ` · ${c.office}` : ""}
              </div>
              {c.description && <div className="small muted mt-0.5">“{c.description}”</div>}
              <div className="small mt-1">
                {c.utility
                  ? <span style={{ color: "var(--green)", fontWeight: 600 }}>Road was dug by {c.utility.agency} (permit #{c.utility.permit_id}) — they must restore it free</span>
                  : c.liable_contractor
                  ? <span style={{ color: "var(--green)", fontWeight: 600 }}>Under guarantee — {c.liable_contractor} must repair free (until {fdate(c.liable_until)})</span>
                  : <span className="muted">Department pays for this repair</span>}
                {c.assigned_to && <span className="muted"> · With: {c.assigned_to}</span>}
                {c.reopened_count > 0 && <span style={{ color: "var(--red)" }}> · Citizen said not fixed ×{c.reopened_count}</span>}
                {c.fix_distance_m !== null && c.fix_distance_m !== undefined && <span className={c.fix_distance_m > 1000 ? "" : "muted"} style={c.fix_distance_m > 1000 ? { color: "var(--red)" } : undefined}> · Repair photo taken {c.fix_distance_m < 1000 ? `${c.fix_distance_m} m` : `${(c.fix_distance_m / 1000).toFixed(1)} km`} from the spot</span>}
              </div>
              {idx >= 0 && <div className="steps5">{STEP_TEXT.map((t, i) => <div key={t} className={i <= idx ? "on" : ""}><i />{t}</div>)}</div>}
            </div>
            <div className="acts flex flex-col gap-1.5 items-stretch" style={{ minWidth: 170 }}>
              {field && next && <button className="btn-primary" onClick={() => setAction({ kind: next[0], c })}>{next[1]}</button>}
              {c.status === "fixed" && <span className="small muted text-center">Waiting for the citizen to confirm</span>}
              {c.liable_contractor && ["verified", "assigned"].includes(c.status) && <a className="btn btn-sm" href={`/api/complaints/${c.id}/notice`} target="_blank">Repair notice (PDF)</a>}
              {c.photo_url && <a className="btn btn-sm" href={c.photo_url} target="_blank"><Camera size={14} /> Photo</a>}
              {c.fix_photo_url && <a className="btn btn-sm" href={c.fix_photo_url} target="_blank"><Camera size={14} /> After photo</a>}
            </div>
          </div>
        );
      })}
      {action && <ActionModal {...action} onClose={() => setAction(null)} />}
    </>
  );
}

function ActionModal({ kind, c, onClose }: { kind: "verify" | "assign" | "fix"; c: Complaint; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [cond, setCond] = useState("");
  const [notes, setNotes] = useState("");
  const [assignKind, setAssignKind] = useState(c.utility ? "utility" : c.liable_contractor ? "contractor" : "department");
  const [pos, setPos] = useState<{ lat: number; lng: number } | null>(null);
  const [posMsg, setPosMsg] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [err, setErr] = useState("");
  const done = (msg: string) => { toast(msg); qc.invalidateQueries(); onClose(); };
  const run = async (fn: () => Promise<void>) => { setErr(""); try { await fn(); } catch (e: any) { setErr(e.message); } };

  if (kind === "verify") return (
    <Modal title={`Check on site — ${c.ticket}`} onClose={onClose}>
      <p className="muted">{c.issue_label} at {c.asset_name}{c.km !== null ? `, km ${c.km}` : ""}</p>
      <label>How bad is it? (1 = very bad, 5 = good)</label>
      <select value={cond} onChange={(e) => setCond(e.target.value)}><option value="">—</option>{[5, 4, 3, 2, 1].map((n) => <option key={n}>{n}</option>)}</select>
      <label>Notes</label><textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      {err && <Alert tone="red">{err}</Alert>}
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button className="btn-danger" onClick={() => run(async () => { await api(`/api/complaints/${c.id}/verify`, { json: { approve: false, notes } }); done("Rejected"); })}>Not a real problem</button>
        <button className="btn-primary" onClick={() => run(async () => { await api(`/api/complaints/${c.id}/verify`, { json: { approve: true, condition: cond ? +cond : null, notes } }); done("Verified"); })}>Yes, problem is real</button>
      </div>
    </Modal>
  );
  if (kind === "assign") return (
    <Modal title={`Assign repair — ${c.ticket}`} onClose={onClose}>
      {c.utility && <Alert tone="blue"><b>{c.utility.agency}</b> dug this stretch under permit #{c.utility.permit_id} ({c.utility.purpose}). The utility must restore it at its own cost — not the road contractor and not the department.</Alert>}
      {c.utility ? null : c.liable_contractor
        ? <Alert tone="blue"><b>{c.liable_contractor}</b> is liable for this spot until {fdate(c.liable_until)} (Clause 17-A). Send a defect notice — the repair costs the department <b>₹0</b> and must be done within 15 days.</Alert>
        : <Alert tone="amber">No contractor is liable here — the department pays for this repair.</Alert>}
      <label>Assign to</label>
      <select value={assignKind} onChange={(e) => setAssignKind(e.target.value)}>
        {c.utility && <option value="utility">Utility that dug the road: {c.utility.agency} (₹0)</option>}
        {c.liable_contractor && <option value="contractor">Liable contractor: {c.liable_contractor} (₹0)</option>}
        <option value="department">Department maintenance gang</option>
      </select>
      {err && <Alert tone="red">{err}</Alert>}
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={() => run(async () => {
          await api(`/api/complaints/${c.id}/assign`, { json: { kind: assignKind } });
          if (assignKind === "contractor") window.open(`/api/complaints/${c.id}/notice`, "_blank");
          done(assignKind === "contractor" ? "Defect notice issued" : assignKind === "utility" ? "Restoration notice sent to the utility" : "Assigned");
        })}>Assign</button>
      </div>
    </Modal>
  );
  return (
    <Modal title={`Mark as repaired — ${c.ticket}`} onClose={onClose}>
      <p className="muted">The citizen sees your photo and is asked to confirm. If they say it is not fixed, the ticket reopens.</p>
      <label>After-repair photo (required)</label><input type="file" accept="image/*" capture="environment" onChange={(e) => setPhoto(e.target.files?.[0] || null)} />
      <div className="small mt-1.5">
        {pos ? <span style={{ color: "var(--green)" }}>✓ Location added — Pravi checks the photo was taken at the spot</span> :
          <button type="button" className="btn-sm" onClick={() => {
            if (!navigator.geolocation) { setPosMsg("Location not available on this device"); return; }
            setPosMsg("Getting location…");
            navigator.geolocation.getCurrentPosition((p) => { setPos({ lat: p.coords.latitude, lng: p.coords.longitude }); setPosMsg(""); },
              () => setPosMsg("Location permission denied — photo will be saved without it"), { enableHighAccuracy: true, timeout: 10000 });
          }}>Add my current location</button>} <span className="muted">{posMsg}</span>
      </div>
      <label>Notes</label><textarea value={notes} onChange={(e) => setNotes(e.target.value)} />
      {err && <Alert tone="red">{err}</Alert>}
      <div className="actions">
        <button onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={() => run(async () => {
          if (!photo) throw new Error("Add an after-repair photo — it is the proof shown to the citizen");
          const fd = new FormData(); fd.append("notes", notes); fd.append("photo", await compressImage(photo), "photo.jpg");
          if (pos) { fd.append("lat", String(pos.lat)); fd.append("lng", String(pos.lng)); }
          await postForm(`/api/complaints/${c.id}/fix`, fd); done("Marked fixed — waiting for citizen");
        })}>Mark as repaired</button>
      </div>
    </Modal>
  );
}
