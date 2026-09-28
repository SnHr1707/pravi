import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/api";
import { fdate, num } from "../lib/format";
import { ErrorBox, Loading } from "../components/ui";

interface Row {
  name: string; talukas: string[]; road_km: number; complaints_open: number; complaints_overdue: number; fixed_90d: number;
  within_deadline_pct: number | null; median_days_to_fix: number | null; culverts_cleaned: number; culverts: number;
  bridges: number; bridges_inspected: number; roads_not_restored: number;
}
interface Perf { district: string; as_of: string; subdivisions: Row[]; sla: Record<string, string> }

export default function Performance() {
  const q = useQuery({ queryKey: ["performance"], queryFn: () => api<Perf>("/api/public/performance") });
  return (
    <div className="max-w-5xl mx-auto px-4 py-6">
      <div className="small"><Link to="/">← Pravi</Link></div>
      <h1 className="mt-2">How is R&amp;B doing near you?</h1>
      <p style={{ color: "var(--ink-2)" }}>Public scorecard for every sub-division: are complaints fixed on time, were drains cleaned before the monsoon,
        were bridges inspected, and have dug-up roads been restored. Updated live from the department's own records.</p>
      {q.isLoading && <Loading />}
      {q.error && <ErrorBox error={q.error} />}
      {q.data && <>
        <p className="small muted">District: {q.data.district} · as of {fdate(q.data.as_of)} · Repair deadlines: potholes {q.data.sla.pothole}, broken railings {q.data.sla.railing}, others {q.data.sla.other}.</p>
        <div className="grid g3">
          {q.data.subdivisions.map((r) => (
            <div className="card" key={r.name}>
              <h2 className="m-0">{r.name}</h2>
              <div className="small muted mb-2">Talukas: {r.talukas.join(", ")} · {num(r.road_km)} km of road</div>
              <div className="kv">
                <div>Open complaints</div><div><b>{r.complaints_open}</b>{r.complaints_overdue > 0 && <span style={{ color: "var(--red)" }}> · {r.complaints_overdue} past deadline</span>}</div>
                <div>Fixed on time</div><div><b>{r.within_deadline_pct === null ? "—" : `${r.within_deadline_pct}%`}</b> <span className="muted small">of {r.fixed_90d} fixed in 90 days</span></div>
                <div>Typical time to fix</div><div>{r.median_days_to_fix === null ? "—" : `${r.median_days_to_fix} days`}</div>
                <div>Drains cleaned before monsoon</div><div>{r.culverts ? `${r.culverts_cleaned} of ${r.culverts}` : "—"}</div>
                <div>Bridges inspected on time</div><div>{r.bridges ? `${r.bridges_inspected} of ${r.bridges}` : "—"}</div>
                <div>Dug roads not restored</div><div style={r.roads_not_restored ? { color: "var(--red)", fontWeight: 700 } : undefined}>{r.roads_not_restored}</div>
              </div>
            </div>
          ))}
        </div>
      </>}
      <div className="flex gap-3 mt-5 flex-wrap">
        <Link className="btn btn-accent" to="/report">Report a problem</Link>
        <Link className="btn" to="/track">Track my complaint</Link>
      </div>
    </div>
  );
}
