import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { inr } from "../lib/format";
import { Badge, ErrorBox, Loading } from "../components/ui";

interface Row {
  contractor: string; works: number; value: number; active_liabilities: number; defects_in_liability: number;
  defects_open: number; overdue_notices: number; delayed_works: number; avg_fix_days: number | null; risk: "high" | "medium" | "low";
}

export default function Contractors() {
  const q = useQuery({ queryKey: ["contractors"], queryFn: () => api<Row[]>("/api/contractors") });
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  return (
    <>
      <div className="page-head"><div><h1>Contractor scorecard</h1>
        <p>How each contractor performs after the work is paid for — defects during liability, notices ignored, delays. Useful at the next tender evaluation.</p></div></div>
      <div className="card">
        <div className="table-wrap"><table>
          <thead><tr><th>Contractor</th><th className="num">Works</th><th className="num">Value</th><th className="num">Active liabilities</th>
            <th className="num">Defects in liability</th><th className="num">Open defects</th><th className="num">Notices overdue (&gt;15 d)</th>
            <th className="num">Delayed works</th><th className="num">Avg fix (days)</th><th>Risk</th></tr></thead>
          <tbody>
            {q.data.map((r) => (
              <tr key={r.contractor}>
                <td><b>{r.contractor}</b></td><td className="num">{r.works}</td><td className="num">{inr(r.value)}</td>
                <td className="num">{r.active_liabilities}</td><td className="num">{r.defects_in_liability}</td><td className="num">{r.defects_open}</td>
                <td className="num">{r.overdue_notices ? <Badge tone="red">{r.overdue_notices}</Badge> : 0}</td>
                <td className="num">{r.delayed_works ? <Badge tone="amber">{r.delayed_works}</Badge> : 0}</td>
                <td className="num">{r.avg_fix_days ?? "—"}</td>
                <td><Badge tone={{ high: "red", medium: "amber", low: "green" }[r.risk]}>{r.risk}</Badge></td>
              </tr>
            ))}
          </tbody>
        </table></div>
        <p className="small muted">Demo data — all contractor names are fictional.</p>
      </div>
    </>
  );
}
