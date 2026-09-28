import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, postForm } from "../lib/api";
import type { Complaint } from "../lib/types";
import { fdate, fdt } from "../lib/format";
import { Alert, ComplaintStatus, ErrorBox, useToast } from "../components/ui";

const STEPS: [string, string][] = [["open", "Reported"], ["verified", "Verified"], ["assigned", "Repair assigned"], ["fixed", "Fixed"], ["closed", "Closed"]];

export default function Track() {
  const [sp, setSp] = useSearchParams();
  const ticket = sp.get("t") || "";
  const [input, setInput] = useState(ticket);
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["track", ticket], queryFn: () => api<Complaint>(`/api/public/complaints/${encodeURIComponent(ticket)}`), enabled: !!ticket, retry: false });

  const confirm = async (fixed: boolean) => {
    const fd = new FormData(); fd.append("fixed", String(fixed));
    await postForm(`/api/public/complaints/${ticket}/confirm`, fd);
    toast(fixed ? "Thank you for confirming!" : "Sorry — we've reopened it and sent it back for repair.");
    qc.invalidateQueries({ queryKey: ["track", ticket] });
  };
  const c = q.data;
  const idx = c ? (c.status === "closed" ? 5 : STEPS.findIndex(([k]) => k === c.status)) : -1;

  return (
    <div className="min-h-screen" style={{ background: "#eef2f8" }}>
      <div className="max-w-2xl mx-auto px-3.5 pt-4 pb-10">
        <Link to="/" className="flex items-center gap-2 font-extrabold mb-3" style={{ color: "var(--ink)" }}>
          <span className="w-7 h-7 rounded-md grid place-items-center text-white" style={{ background: "var(--accent)" }}>P</span> Track your complaint
        </Link>
        <div className="card">
          <form className="flex gap-2.5" onSubmit={(e) => { e.preventDefault(); setSp({ t: input.trim() }); }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ticket number, e.g. GJ-VAD-10241" required />
            <button className="btn-primary">Track</button>
          </form>
        </div>
        {q.isLoading && <div className="card muted">Loading…</div>}
        {q.error && <ErrorBox error={q.error} />}
        {c && (
          <>
            <div className="card">
              <div className="card-head">
                <div><div className="small muted">Ticket</div><h1 className="m-0">{c.ticket}</h1></div>
                <ComplaintStatus s={c.status} />
              </div>
              <div className="kv">
                <div>Problem</div><div>{c.issue_label}{c.report_count > 1 ? ` · reported by ${c.report_count} people` : ""}</div>
                <div>Location</div><div>{c.asset_name}{c.km !== null ? ` · km ${c.km}` : ""}</div>
                <div>Reported</div><div>{fdt(c.created_at)}</div>
                {c.assigned_to && <><div>Being fixed by</div><div>{c.assigned_to}</div></>}
                {c.sla && c.sla.state !== "na" && <><div>Repair deadline</div><div>{fdt(c.sla.due)} ({c.sla.hours < 48 ? `${c.sla.hours} hours` : `${c.sla.hours / 24} days`})
                  {c.sla.state === "overdue" && <span style={{ color: "var(--red)" }}> · late{c.sla.escalated_label ? ` — escalated to the ${c.sla.escalated_label}` : ""}</span>}
                  {c.sla.state === "met" && <span style={{ color: "var(--green)" }}> · fixed on time</span>}</div></>}
              </div>
              {c.status === "rejected" ? (
                <Alert tone="amber">This report was closed by the engineer (not an R&amp;B asset, or a duplicate).</Alert>
              ) : (
                <div className="flex justify-between my-5 relative">
                  <div className="absolute left-[6%] right-[6%] top-3.5 h-[3px]" style={{ background: "#dbe3ef" }} />
                  {STEPS.map(([k, l], i) => {
                    const doneStep = i < idx, now = i === idx;
                    return (
                      <div key={k} className="flex-1 text-center relative text-xs" style={{ color: doneStep || now ? "var(--ink)" : "var(--ink-3)", fontWeight: doneStep ? 600 : 400 }}>
                        <div className="w-7 h-7 rounded-full mx-auto mb-1 grid place-items-center text-white font-bold"
                          style={{ background: doneStep ? "var(--green)" : now ? "var(--brand)" : "#dbe3ef", boxShadow: now ? "0 0 0 4px #c9d8f2" : undefined }}>
                          {doneStep ? "✓" : i + 1}
                        </div>{l}
                      </div>
                    );
                  })}
                </div>
              )}
              {c.liable_contractor && (
                <Alert tone="green">This road is still under the contractor's guarantee (until {fdate(c.liable_until)}). <b>{c.liable_contractor}</b> must repair it at no cost to the public.</Alert>
              )}
              {c.status === "fixed" && (
                <Alert tone="blue">
                  <b>The department says this is fixed.</b> Is it really fixed?
                  <div className="flex gap-2.5 mt-2.5">
                    <button className="btn-primary" onClick={() => confirm(true)}>Yes, it's fixed</button>
                    <button className="btn-danger" onClick={() => confirm(false)}>No, still broken</button>
                  </div>
                </Alert>
              )}
              {(c.photo_url || c.fix_photo_url) && (
                <div className="grid grid-cols-2 gap-2.5 mt-2.5">
                  {c.photo_url && <div><div className="small muted">Your photo</div><img src={c.photo_url} className="w-full rounded-lg" /></div>}
                  {c.fix_photo_url && <div><div className="small muted">After repair</div><img src={c.fix_photo_url} className="w-full rounded-lg" /></div>}
                </div>
              )}
            </div>
            <div className="card">
              <h3>History</h3>
              <div className="timeline">
                {c.events?.map((e, i) => (
                  <div key={i} className="tl-item" style={{ ["--c" as any]: "#274b8a" }}><div>{e.message}</div><div className="when">{fdt(e.at)}</div></div>
                ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
