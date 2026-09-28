import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { api } from "../lib/api";
import type { AssetRow, Work } from "../lib/types";
import { STAGES, STATUS_LABEL, WORK_TYPES, fdate, inr } from "../lib/format";
import { Alert, ErrorBox, Loading, Modal, SevBadge, useToast } from "../components/ui";
import { Can, useMe } from "../components/StaffLayout";

type Warn = { message: string } | null;

export default function Works() {
  const q = useQuery({ queryKey: ["works"], queryFn: () => api<Work[]>("/api/works") });
  const [sp, setSp] = useSearchParams();
  const [open, setOpen] = useState<Work | null>(null);
  const [propose, setPropose] = useState<string | null>(sp.get("propose"));
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const recent = (w: Work) => w.status !== "completed" || (!!w.completed_on && (Date.now() - new Date(w.completed_on).getTime()) / 864e5 < 400);

  return (
    <>
      <div className="page-head">
        <div><h1>Works &amp; tenders</h1>
          <p>Every work moves left to right. Click a card to move it to the next step. When a work is completed, its guarantee period starts.</p></div>
        <Can roles={["engineer", "ee"]}><button className="btn-primary" onClick={() => setPropose("")}><Plus size={16} />Propose new work</button></Can>
      </div>
      <div className="board">
        {STAGES.map((s) => {
          const list = q.data.filter((w) => w.status === s && recent(w));
          return (
            <div className="col" key={s}>
              <h3><span>{STATUS_LABEL[s]}</span><span>{list.length}</span></h3>
              {list.map((w) => (
                <div className="wcard" key={w.id} onClick={() => setOpen(w)}>
                  <div className="t">{w.title}</div>
                  <div className="small muted">{w.asset_code}{w.contractor ? ` · ${w.contractor}` : ""}</div>
                  <div className="small">{inr(w.awarded_cost || w.estimated_cost)}{w.due_on && w.status !== "completed" ? ` · due ${fdate(w.due_on)}` : ""}{w.liability_end ? ` · liable → ${fdate(w.liability_end)}` : ""}</div>
                  {w.flags?.map((f, i) => <div key={i} className="mt-1"><SevBadge sev={f.severity} /> <span className="small">{f.title}</span></div>)}
                </div>
              ))}
            </div>
          );
        })}
      </div>
      {open && <WorkModal w={open} onClose={() => setOpen(null)} />}
      {propose !== null && <ProposeModal assetId={propose} onClose={() => { setPropose(null); setSp({}); }} />}
    </>
  );
}

function WorkModal({ w, onClose }: { w: Work; onClose: () => void }) {
  const me = useMe().data;
  const qc = useQueryClient();
  const toast = useToast();
  const i = STAGES.indexOf(w.status);
  const next = STAGES[i + 1];
  const canAct = !!me && ["engineer", "ee"].includes(me.role) && !!next && (next !== "sanctioned" || me.role === "ee");
  const [warn, setWarn] = useState<Warn>(null);
  const [err, setErr] = useState("");

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setErr("");
    const body: Record<string, string> = { to: next };
    new FormData(e.currentTarget).forEach((v, k) => { if (v !== "") body[k] = String(v); });
    try {
      const r = await api<Work & { liability_warning: Warn }>(`/api/works/${w.id}/advance`, { json: body });
      qc.invalidateQueries();
      if (r.liability_warning) { setWarn(r.liability_warning); toast("Saved — but check the liability warning"); }
      else { toast("Moved to " + STATUS_LABEL[next]); onClose(); }
    } catch (x: any) { setErr(x.message); }
  };
  const cancel = async () => {
    await api(`/api/works/${w.id}/advance`, { json: { to: "cancelled", reason: "Cancelled by EE" } });
    qc.invalidateQueries(); toast("Work cancelled"); onClose();
  };
  const today = new Date().toISOString().slice(0, 10);
  return (
    <Modal title={w.title} onClose={onClose}>
      <div className="stepper">{STAGES.map((s, j) => <div key={s} className={`s ${j < i ? "done" : j === i ? "on" : ""}`} title={STATUS_LABEL[s]} />)}</div>
      <div className="kv my-2.5">
        <div>Asset</div><div><Link to={`/app/assets/${w.asset_id}`}>{w.asset_name}</Link></div>
        <div>Type</div><div>{w.work_label}{w.start_km !== null ? ` · km ${w.start_km}–${w.end_km}` : ""}</div>
        <div>Stage</div><div>{STATUS_LABEL[w.status]}</div>
        {w.tender_id && <><div>Tender</div><div>{w.tender_id}</div></>}
        {w.contractor && <><div>Contractor</div><div>{w.contractor}</div></>}
        <div>Cost</div><div>est. {inr(w.estimated_cost)}{w.awarded_cost ? ` · awarded ${inr(w.awarded_cost)}` : ""}</div>
        {w.liability_end && <><div>Liability</div><div>{w.liability_months} months → {fdate(w.liability_end)}</div></>}
        {w.reason && <><div>Reason</div><div>{w.reason}</div></>}
      </div>
      {w.flags?.map((f, k) => <Alert key={k} tone={f.severity === "red" ? "red" : "amber"}>{f.title}</Alert>)}
      {canAct ? (
        <form onSubmit={submit}>
          <h3 className="mt-3">Move to: {STATUS_LABEL[next]}</h3>
          {next === "sanctioned" && <><label>Sanctioned estimate (₹)</label><input name="estimated_cost" type="number" defaultValue={w.estimated_cost ?? ""} /></>}
          {next === "tendered" && <div className="row">
            <div><label>Tender ID</label><input name="tender_id" defaultValue={w.tender_id ?? ""} placeholder="auto" /></div>
            <div><label>Defects liability (months, Clause 17-A)</label><input name="liability_months" type="number" defaultValue={w.liability_months ?? ""} /></div></div>}
          {next === "awarded" && <>
            <label>Contractor</label><input name="contractor" required />
            <div className="row"><div><label>Contract value (₹)</label><input name="awarded_cost" type="number" defaultValue={w.estimated_cost ?? ""} /></div>
              <div><label>Time limit (days)</label><input name="completion_period_days" type="number" /></div></div></>}
          {next === "completed" && <><label>Defects liability (months)</label><input name="liability_months" type="number" defaultValue={w.liability_months ?? ""} /></>}
          <label>Date</label><input name="date" type="date" defaultValue={today} />
          {warn && <Alert tone="red"><b>Liability warning:</b> {warn.message}</Alert>}
          {err && <Alert tone="red">{err}</Alert>}
          <div className="actions">
            {me?.role === "ee" && <button type="button" className="btn-danger" onClick={cancel}>Cancel work</button>}
            <button type="button" onClick={onClose}>Close</button>
            <button className="btn-primary">Move to {STATUS_LABEL[next]}</button>
          </div>
        </form>
      ) : <div className="actions"><button onClick={onClose}>Close</button></div>}
    </Modal>
  );
}

function ProposeModal({ assetId, onClose }: { assetId: string; onClose: () => void }) {
  const assetsQ = useQuery({ queryKey: ["assets"], queryFn: () => api<AssetRow[]>("/api/assets") });
  const qc = useQueryClient();
  const toast = useToast();
  const [aid, setAid] = useState(assetId);
  const [warn, setWarn] = useState<Warn>(null);
  const [err, setErr] = useState("");
  const [saved, setSaved] = useState(false);
  const assets = (assetsQ.data || []).slice().sort((a, b) => a.code.localeCompare(b.code));
  useEffect(() => { if (!aid && assets.length) setAid(String(assets[0].id)); }, [assets.length]);
  const sel = assets.find((a) => String(a.id) === aid);

  const submit = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); setErr("");
    const body: Record<string, string> = {};
    new FormData(e.currentTarget).forEach((v, k) => (body[k] = String(v)));
    try {
      const r = await api<{ liability_warning: Warn }>("/api/works", { json: body });
      qc.invalidateQueries();
      if (r.liability_warning) { setWarn(r.liability_warning); setSaved(true); }
      else { toast("Work proposed"); onClose(); }
    } catch (x: any) { setErr(x.message); }
  };
  return (
    <Modal title="Propose work" onClose={onClose}>
      <form onSubmit={submit}>
        <label>Asset</label>
        <select name="asset_id" value={aid} onChange={(e) => setAid(e.target.value)} required>
          {assets.map((a) => <option key={a.id} value={a.id}>{a.code} · {a.name}</option>)}
        </select>
        <label>Work type</label>
        <select name="work_type">{Object.entries(WORK_TYPES).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <label>Name of work</label><input name="title" placeholder="e.g. Special repair to … Km. 4/0 to 8/0" />
        {sel?.type === "road_section" && <div className="row">
          <div><label>From km</label><input name="start_km" type="number" step="0.001" placeholder={String(sel.start_km)} /></div>
          <div><label>To km</label><input name="end_km" type="number" step="0.001" placeholder={String(sel.end_km)} /></div></div>}
        <div className="row">
          <div><label>Estimated cost (₹)</label><input name="estimated_cost" type="number" /></div>
          <div><label>Defects liability (months)</label><input name="liability_months" type="number" placeholder="e.g. 36" /></div></div>
        <label>Reason</label><textarea name="reason" />
        {warn && <><Alert tone="red"><b>Liability warning:</b> {warn.message}</Alert>
          <p className="small">The proposal was saved and flagged. Consider issuing a defect notice instead.</p></>}
        {err && <Alert tone="red">{err}</Alert>}
        <div className="actions"><button type="button" onClick={onClose}>{saved ? "Close" : "Cancel"}</button>
          {!saved && <button className="btn-primary">Propose</button>}</div>
      </form>
    </Modal>
  );
}
