import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, setViewOffice } from "../lib/api";
import type { OfficeBrief } from "../lib/types";
import { inr, num } from "../lib/format";
import { useMe } from "../components/StaffLayout";
import { ErrorBox, Loading } from "../components/ui";

interface Stats {
  assets: number; road_km: number; urgent: number; red_flags: number; open_complaints: number; overdue_complaints: number;
  escalated: number; fixed_90d: number; within_deadline_pct: number | null; money_at_risk: number; culverts_cleaned: number;
  culverts: number; awaiting_approval: number; roads_not_restored: number;
}
interface Unit extends OfficeBrief { stats: Stats | null; officers: { name: string; role: string }[] }
interface View {
  office: OfficeBrief; breadcrumb: OfficeBrief[]; officers: { name: string; role: string }[]; total: Stats;
  units: Unit[]; child_level: string | null; approval_limits: { role: string; label: string; limit: number | null }[];
}

const LADDER = [
  ["Secretary (R&B)", "Whole department"],
  ["Chief Engineer", "One wing — State roads, Panchayat roads, National Highways …"],
  ["Superintending Engineer", "One circle — 3 to 5 divisions"],
  ["Executive Engineer", "One division — usually a district"],
  ["Deputy Executive Engineer", "One sub-division — one or more talukas"],
  ["Additional Assistant Engineer", "One section — field inspections and site work"],
];

export default function Offices() {
  const q = useQuery({ queryKey: ["offices"], queryFn: () => api<View>("/api/offices") });
  const me = useMe().data;
  const qc = useQueryClient();
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const v = q.data;
  const allowed = new Set((me?.offices || []).map((o) => o.id));
  const go = (id: number) => { setViewOffice(me && id === me.home.id ? null : id); qc.invalidateQueries(); };
  const t = v.total;

  return (
    <>
      <div className="page-head">
        <div>
          <div className="crumbs">
            {v.breadcrumb.map((o, i) => (
              <span key={o.id}>{i > 0 && "› "}{allowed.has(o.id) && o.id !== v.office.id
                ? <button onClick={() => go(o.id)}>{o.name}</button> : <b>{o.name}</b>}</span>
            ))}
          </div>
          <h1>{v.office.name}</h1>
          <p>{v.office.level_label} headed by the {v.office.head}{v.officers.length ? ` — ${v.officers.map((o) => o.name).join(", ")}` : ""}.
            {v.child_level ? ` Compare the ${v.child_level.toLowerCase()}s under it and click one to look inside.` : ""}</p>
        </div>
      </div>

      <div className="kpis" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
        <div className="kpi"><div className="v">{t.assets}</div><div className="l">assets · {num(t.road_km)} km road</div></div>
        <div className="kpi red"><div className="v">{t.overdue_complaints}</div><div className="l">complaints past deadline</div></div>
        <div className="kpi amber"><div className="v">{t.within_deadline_pct === null ? "—" : `${t.within_deadline_pct}%`}</div><div className="l">repaired within deadline (90 days)</div></div>
        <div className="kpi blue"><div className="v">{t.awaiting_approval}</div><div className="l">works waiting for approval</div></div>
        <div className="kpi red"><div className="v">{inr(t.money_at_risk)}</div><div className="l">at risk of double payment</div></div>
      </div>

      {v.units.length > 0 && (
        <div className="card">
          <h2>{v.child_level}s under {v.office.name}</h2>
          <div className="table-wrap"><table className="league">
            <thead><tr><th>{v.child_level}</th><th>Officer</th><th>Assets</th><th>Fix soon</th><th>Open complaints</th><th>Past deadline</th>
              <th>On-time repairs</th><th>Culverts cleaned</th><th>Waiting approval</th><th>₹ at risk</th></tr></thead>
            <tbody>
              {v.units.map((u) => u.stats ? (
                <tr key={u.id}>
                  <td>{allowed.has(u.id) ? <button className="btn-sm" onClick={() => go(u.id)}><b>{u.name}</b> →</button> : <b>{u.name}</b>}
                    {u.talukas.length > 0 && <div className="small muted">{u.talukas.join(", ")}</div>}</td>
                  <td className="small">{u.officers.map((o) => o.name).join(", ") || <span className="muted">{u.head}</span>}</td>
                  <td>{u.stats.assets}<div className="small muted">{num(u.stats.road_km)} km</div></td>
                  <td>{u.stats.urgent}</td>
                  <td>{u.stats.open_complaints}</td>
                  <td style={u.stats.overdue_complaints ? { color: "var(--red)", fontWeight: 700 } : undefined}>{u.stats.overdue_complaints}</td>
                  <td>{u.stats.within_deadline_pct === null ? "—" : `${u.stats.within_deadline_pct}%`}</td>
                  <td>{u.stats.culverts ? `${u.stats.culverts_cleaned}/${u.stats.culverts}` : "—"}</td>
                  <td>{u.stats.awaiting_approval}</td>
                  <td>{inr(u.stats.money_at_risk)}</td>
                </tr>
              ) : (
                <tr key={u.id} className="off"><td><b>{u.name}</b></td><td className="small">{u.head}</td><td colSpan={8} className="small">Not on Pravi yet — onboarded the same way, one division at a time</td></tr>
              ))}
            </tbody>
          </table></div>
        </div>
      )}

      <div className="grid g2 mt-4">
        <div className="card">
          <h2>Chain of command in R&amp;B</h2>
          {LADDER.map(([r, w], i) => (
            <div className="li-row" key={r} style={{ paddingLeft: i * 14 }}>
              <div><b>{r}</b><div className="small muted">{w}</div></div>
            </div>
          ))}
          <p className="small muted mb-0">Each officer sees their own office and everything below it. Late complaints climb this ladder automatically.</p>
        </div>
        <div className="card">
          <h2>Who approves a work?</h2>
          <p className="small muted mt-0">A proposal goes to the lowest officer whose sanction limit covers the cost (illustrative limits — set from the state's delegation of powers).</p>
          <table><tbody>
            {v.approval_limits.map((a) => <tr key={a.role}><td>{a.label}</td><td><b>{a.limit === null ? "Above that" : `up to ${inr(a.limit)}`}</b></td></tr>)}
          </tbody></table>
          <h3 className="mt-4">When is a complaint escalated?</h3>
          <table><tbody>
            <tr><td>Deadline</td><td>Pothole / waterlogging 48 h (24 h in monsoon) · broken railing 24 h · others 7 days</td></tr>
            <tr><td>Late</td><td>goes to the Executive Engineer</td></tr>
            <tr><td>3× late</td><td>goes to the Superintending Engineer</td></tr>
            <tr><td>7× late</td><td>goes to the Chief Engineer</td></tr>
          </tbody></table>
        </div>
      </div>
    </>
  );
}
