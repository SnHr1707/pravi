import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { inr, num } from "../lib/format";
import { Badge, ErrorBox, Kpi, Loading } from "../components/ui";

interface Cand {
  asset_id: number; asset_code: string; title: string; kind: string; source: string; cost: number; daily_users: number;
  value: number | null; reason: string; rural: boolean; early?: boolean; condition: number | null;
}
interface Plan {
  budget: number; spent: number; left: number;
  summary: { works_funded: number; daily_users_benefiting: number; future_cost_avoided: number; free_fixes: number;
    blocked_payments: number; rural_works: number; rural_spend: number };
  free: Cand[]; blocked: Cand[]; funded: Cand[]; deferred: Cand[];
  assumptions: Record<string, any>;
}

function Table({ list }: { list: Cand[] }) {
  return (
    <div className="table-wrap"><table>
      <thead><tr><th>#</th><th>Work</th><th>Asset</th><th className="num">Cost</th><th className="num">Daily users</th><th className="num">Benefit per ₹ crore</th><th>Why</th></tr></thead>
      <tbody>
        {list.map((c, i) => (
          <tr key={c.asset_code + c.title}>
            <td>{i + 1}</td>
            <td><b>{c.title}</b>{" "}
              {c.source === "suggested" && <Badge>suggested</Badge>}{c.source === "proposal" && <Badge tone="blue">proposal</Badge>}{" "}
              {c.rural && <Badge tone="green">rural</Badge>} {c.early && <Badge tone="yellow">early action</Badge>}</td>
            <td><Link to={`/app/assets/${c.asset_id}`}>{c.asset_code}</Link>{c.condition && <div className="small muted">condition {c.condition}/5</div>}</td>
            <td className="num">{inr(c.cost)}</td>
            <td className="num">{c.daily_users ? num(c.daily_users) : "—"}</td>
            <td className="num">{c.value ? num(Math.round(c.value)) : "—"}</td>
            <td className="small">{c.reason}</td>
          </tr>
        ))}
        {!list.length && <tr><td colSpan={7} className="muted">None</td></tr>}
      </tbody>
    </table></div>
  );
}

export default function Planner() {
  const [budget, setBudget] = useState(10);
  const [rural, setRural] = useState(25);
  const [params, setParams] = useState({ budget: 10, rural: 25 });
  const q = useQuery({
    queryKey: ["planner", params],
    queryFn: () => api<Plan>(`/api/planner?budget_cr=${params.budget}&rural_share=${params.rural}`),
  });
  const p = q.data;
  const a = p?.assumptions;
  return (
    <>
      <div className="page-head"><div><h1>Budget plan</h1>
        <p>Enter this year's budget. Pravi suggests what to fund: free repairs first, then safety, then the works that help the most people per rupee — keeping a share for village roads.</p></div></div>
      <div className="card">
        <form className="flex gap-4 items-end flex-wrap" onSubmit={(e) => { e.preventDefault(); setParams({ budget, rural }); }}>
          <div style={{ width: 200 }}><label>Budget (₹ crore)</label><input type="number" step="0.5" min="0.5" value={budget} onChange={(e) => setBudget(+e.target.value)} /></div>
          <div style={{ width: 340 }}><label>Reserved for rural roads (ODR / village): {rural}%</label>
            <input type="range" min={0} max={60} step={5} value={rural} onChange={(e) => setRural(+e.target.value)} className="p-0" /></div>
          <button className="btn-primary">Make plan</button>
        </form>
      </div>
      {q.isLoading && <Loading label="Planning…" />}
      {q.error && <ErrorBox error={q.error} />}
      {p && (
        <>
          <div className="kpis mt-4">
            <Kpi value={inr(p.spent)} label={`allocated of ${inr(p.budget)}`} />
            <Kpi tone="green" value={p.summary.works_funded} label={`works funded (${p.summary.rural_works} rural, ${inr(p.summary.rural_spend)})`} />
            <Kpi tone="blue" value={num(p.summary.daily_users_benefiting)} label="daily road/building users benefit" />
            <Kpi tone="green" value={inr(p.summary.future_cost_avoided)} label="expected future rebuild cost avoided" />
            <Kpi tone="blue" value={p.summary.free_fixes} label="free fixes via contractor liability" />
            <Kpi tone="red" value={inr(p.summary.blocked_payments)} label="payments blocked (contractor liable)" />
          </div>
          <div className="card"><h2>1 · Free fixes — contractor pays</h2><Table list={p.free} /></div>
          <div className="card"><h2>2 · Do not pay — stretch still under liability</h2><Table list={p.blocked} /></div>
          <div className="card"><h2>3 · Funded</h2><Table list={p.funded} /></div>
          <div className="card"><h2>4 · Deferred</h2><Table list={p.deferred} /></div>
        </>
      )}
      <div className="card mt-4">
        <h2>How the plan is made</h2>
        <ol className="small list-decimal pl-5 leading-7 m-0">
          <li><b>Free fixes (₹0):</b> defects on assets still under a contractor's Clause 17-A liability go to the contractor.</li>
          <li><b>Blocked payments:</b> paid works on stretches still under liability are held — that money is saved.</li>
          <li><b>Safety first:</b> urgent bridges and critical buildings in poor condition are funded before anything else.</li>
          <li><b>Value per rupee:</b> <span className="mono">daily users × need × criticality × length × early-action bonus ÷ cost</span>. Fixing a road at condition 2–3 costs a resurfacing; waiting until it fails costs a rebuild (~3×).</li>
          <li><b>Rural reserve:</b> a share of the budget is ranked separately among village and other district roads, so low-traffic villages are not always last.</li>
        </ol>
        {a && <p className="small muted">Assumptions (illustrative, configurable): resurfacing ₹/km — SH {inr(a.recarpet_rate_per_km.SH)}, MDR {inr(a.recarpet_rate_per_km.MDR)}, ODR {inr(a.recarpet_rate_per_km.ODR)}, VR {inr(a.recarpet_rate_per_km.VR)}; reconstruction {a.reconstruct_factor}× resurfacing; failure probability if deferred {a.failure_probability}; early-action bonus {a.early_action_bonus}×; bridge rehab {inr(a.bridge_rehab)}; culvert fix {inr(a.culvert_fix)}.</p>}
      </div>
    </>
  );
}
