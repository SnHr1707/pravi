import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Polyline } from "react-leaflet";
import { api } from "../lib/api";
import type { AssetRow, Flag } from "../lib/types";
import { BAND_COLOR, TYPE_LABEL, fdate, inr, num } from "../lib/format";
import { BAND_TEXT } from "../lib/labels";
import { AssetShape, BaseMap, FitBounds } from "../components/AssetMap";
import { BandBadge, ErrorBox, FlagCard, Loading, ScoreBox } from "../components/ui";
import { useMe } from "../components/StaffLayout";

interface Dash {
  district: string;
  kpis: Record<string, number> & { by_type: Record<string, number> };
  flags: Flag[]; top: AssetRow[]; assets: AssetRow[];
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

export default function Dashboard() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => api<Dash>("/api/dashboard") });
  const me = useMe().data;
  const [showLiab, setShowLiab] = useState(false);
  const [allAlerts, setAllAlerts] = useState(false);
  if (q.isLoading) return <Loading />;
  if (q.error || !q.data) return <ErrorBox error={q.error} />;
  const d = q.data, k = d.kpis;
  const pts = d.assets.flatMap((a) => (a.geometry ? a.geometry : a.lat !== null ? [[a.lat, a.lng!] as [number, number]] : []));
  const urgentFlags = d.flags.filter((f) => f.severity === "red");
  const shownFlags = allAlerts ? d.flags : urgentFlags.slice(0, 4);

  // The to-do list: only things someone should act on, in plain words
  const todos = [
    { n: k.new_complaints, t: "New complaints to check on site", s: "Citizens reported these", to: "/app/complaints", c: "var(--accent)" },
    { n: k.to_assign, t: "Checked complaints to assign", s: "Send to contractor or department", to: "/app/complaints", c: "var(--brand-2)" },
    { n: k.paid_in_liability, t: `Stop payments worth ${inr(k.money_at_risk)}`, s: "The contractor must repair these for free", to: "/app/works", c: "var(--red)" },
    { n: k.notices_ignored, t: "Contractors ignoring repair notices", s: "Escalate — more than 15 days", to: "/app/complaints", c: "var(--red)" },
    { n: k.urgent, t: "Unsafe structures", s: "Bridge or building needs urgent action", to: "/app/assets", c: "#b42318" },
    { n: k.docs_to_review, t: "Documents waiting for your check", s: "Uploaded but not saved yet", to: "/app/documents", c: "var(--brand-2)" },
    { n: k.delayed_works, t: "Works running late", s: "Past their completion date", to: "/app/works", c: "var(--amber)" },
  ].filter((x) => x.n > 0);

  return (
    <>
      <div className="page-head">
        <div>
          <h1>{greeting()}{me ? `, ${me.name.split(" (")[0]}` : ""}</h1>
          <p>Here is what needs attention in R&amp;B {d.district} today.</p>
        </div>
      </div>

      <h2>Your to-do list</h2>
      <div className="todo">
        {todos.length ? todos.map((x) => (
          <Link key={x.t} to={x.to} style={{ ["--c" as any]: x.c }}>
            <span className="n">{x.n}</span><span><span className="t">{x.t}</span><br /><span className="s">{x.s}</span></span>
          </Link>
        )) : <Link to="/app/assets" className="done"><span className="n">✓</span><span className="t">All caught up</span></Link>}
      </div>

      <div className="grid g-main">
        <div className="card">
          <div className="card-head">
            <h2 className="m-0">Map of all assets</h2>
            <label className="m-0 flex gap-1.5 items-center font-medium">
              <input type="checkbox" className="w-auto" checked={showLiab} onChange={(e) => setShowLiab(e.target.checked)} /> Show roads under guarantee
            </label>
          </div>
          <p className="small muted mt-0">Colour shows how soon each road, bridge or building needs work. Click anything for details.</p>
          <BaseMap height={480}>
            <FitBounds points={pts} />
            {d.assets.map((a) => (
              <AssetShape key={a.id} a={a} color={BAND_COLOR[a.band]}>
                <b>{a.name}</b><br />{TYPE_LABEL[a.type]} · {BAND_TEXT[a.band]}<br />
                {a.under_liability && <>Under guarantee: {a.liable_contractor} repairs free until {fdate(a.liable_until)}<br /></>}
                <i>{a.action}</i><br /><Link to={`/app/assets/${a.id}`}>Open →</Link>
              </AssetShape>
            ))}
            {showLiab && d.assets.filter((a) => a.under_liability && a.geometry).map((a) => (
              <Polyline key={"l" + a.id} positions={a.geometry!} pathOptions={{ color: "#1f5fbf", weight: 3, dashArray: "6 6" }} />
            ))}
          </BaseMap>
          <div className="legend">
            {(["Urgent", "This month", "Next season", "Monitor"] as const).map((b) => (
              <span key={b}><i className="dot" style={{ background: BAND_COLOR[b] }} />{BAND_TEXT[b]}</span>
            ))}
            <span><i style={{ display: "inline-block", width: 22, borderTop: "3px dashed #1f5fbf" }} />Under guarantee (free repair)</span>
          </div>
        </div>
        <div className="card">
          <div className="card-head"><h2 className="m-0">Fix these first</h2><Link className="small" to="/app/assets">See all →</Link></div>
          {d.top.slice(0, 6).map((a) => (
            <Link to={`/app/assets/${a.id}`} className="li-row" key={a.id} style={{ color: "var(--ink)", textDecoration: "none" }}>
              <ScoreBox score={a.score} band={a.band} />
              <div className="flex-1 min-w-0">
                <b>{a.name}</b>
                <div className="mt-1"><BandBadge band={a.band} /></div>
                <div className="small mt-1" style={{ color: "var(--brand-2)", fontWeight: 600 }}>→ {a.action}</div>
              </div>
            </Link>
          ))}
          <p className="small muted mb-0">The number is a priority score out of 100 — higher means fix sooner.</p>
        </div>
      </div>

      <div className="card mt-4">
        <div className="card-head">
          <h2 className="m-0">Alerts {allAlerts ? `(${d.flags.length})` : `— ${urgentFlags.length} urgent`}</h2>
          <button className="btn-sm" onClick={() => setAllAlerts(!allAlerts)}>{allAlerts ? "Show urgent only" : `Show all ${d.flags.length} alerts`}</button>
        </div>
        <div className="grid g2 gap-x-4 gap-y-0">{shownFlags.map((f) => <FlagCard key={f.key} f={f} />)}</div>
      </div>

      <div className="kpis mt-4" style={{ gridTemplateColumns: "repeat(auto-fit, minmax(170px, 1fr))" }}>
        <div className="kpi"><div className="v">{k.assets}</div><div className="l">assets tracked · {num(k.road_km)} km of road</div></div>
        <div className="kpi blue"><div className="v">{num(k.road_km_under_liability)} km</div><div className="l">of road under contractor guarantee</div></div>
        <div className="kpi amber"><div className="v">{k.open_complaints}</div><div className="l">open complaints</div></div>
        <div className="kpi red"><div className="v">{inr(k.money_at_risk)}</div><div className="l">at risk of being paid twice</div></div>
      </div>
    </>
  );
}
