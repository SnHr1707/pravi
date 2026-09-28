import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import type { AssetRow } from "../lib/types";
import { TYPE_LABEL, fdate } from "../lib/format";
import { BandBadge, Badge, ErrorBox, Loading, ScoreBox } from "../components/ui";

const TYPES: [string, string][] = [["all", "All"], ["road_section", "Roads"], ["bridge", "Bridges"], ["culvert", "Culverts & drains"], ["building", "Buildings"]];

export default function Assets() {
  const [sp, setSp] = useSearchParams();
  const type = sp.get("type") || "all";
  const [q, setQ] = useState("");
  const res = useQuery({ queryKey: ["assets"], queryFn: () => api<AssetRow[]>("/api/assets") });
  if (res.isLoading) return <Loading />;
  if (res.error || !res.data) return <ErrorBox error={res.error} />;
  const all = res.data;
  const count = (t: string) => (t === "all" ? all.length : all.filter((a) => a.type === t).length);
  const rows = all.filter((a) => (type === "all" || a.type === type) && (!q || (a.name + a.code).toLowerCase().includes(q.toLowerCase())));

  return (
    <>
      <div className="page-head"><div><h1>Roads &amp; buildings</h1>
        <p>Everything R&amp;B looks after, most urgent first. Click a name to see its full history.</p></div></div>
      <div className="card">
        <div className="flex gap-2.5 mb-3 flex-wrap items-center">
          <div className="tabs m-0 flex-1">
            {TYPES.map(([k, l]) => <button key={k} className={k === type ? "on" : ""} onClick={() => setSp(k === "all" ? {} : { type: k })}>{l} ({count(k)})</button>)}
          </div>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name or code…" style={{ maxWidth: 280 }} />
        </div>
        <div className="table-wrap"><table>
          <thead><tr><th>Priority</th><th>Name</th><th>Type</th><th>Condition</th><th>Who pays for repairs</th><th>Complaints</th><th>Alerts</th><th>What to do</th></tr></thead>
          <tbody>
            {rows.map((a) => (
              <tr key={a.id}>
                <td><div className="flex gap-2 items-center"><ScoreBox score={a.score} band={a.band} /><BandBadge band={a.band} /></div></td>
                <td><Link to={`/app/assets/${a.id}`}><b>{a.name}</b></Link><div className="small muted">{a.code}{a.taluka ? ` · Ta. ${a.taluka}` : ""}</div></td>
                <td>{TYPE_LABEL[a.type]}</td>
                <td>{a.condition ? `${a.condition}/5` : "—"}</td>
                <td>{a.under_liability ? <Badge tone="green" title="Contractor must fix defects free">Contractor (free) until {fdate(a.liable_until)}</Badge> : <span className="small muted">Department</span>}</td>
                <td>{a.open_complaints || "—"}</td>
                <td className="whitespace-nowrap">{a.red_flags > 0 && <Badge tone="red">{a.red_flags}</Badge>} {a.flags - a.red_flags > 0 && <Badge>{a.flags - a.red_flags}</Badge>}</td>
                <td className="small">{a.action}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </div>
    </>
  );
}
