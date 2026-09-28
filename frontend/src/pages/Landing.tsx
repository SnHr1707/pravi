import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Building2, HardHat, Smartphone } from "lucide-react";

export default function Landing() {
  const [t, setT] = useState("");
  const nav = useNavigate();
  return (
    <div>
      <section className="text-white px-5 pt-12 pb-16" style={{ background: "linear-gradient(135deg,#1d3a6e 0%,#274b8a 60%,#2f5ea8 100%)" }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-center gap-2.5 font-extrabold text-lg mb-9">
            <span className="w-9 h-9 rounded-lg grid place-items-center" style={{ background: "var(--accent)" }}>P</span>
            Pravi <span className="font-medium text-sm" style={{ color: "#b9c9e6" }}>Roads &amp; Buildings Asset Tracker · Gujarat</span>
          </div>
          <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight mb-3">Every public asset, one lifelong record.</h1>
          <p className="text-lg max-w-2xl mb-6" style={{ color: "#d6e1f5" }}>
            Roads, bridges, culverts and government buildings — tracked from proposal to repair, built from the contracts R&amp;B already signs.
            Know who must fix what, what to fix first, and where each rupee does the most good.
          </p>
          <div className="flex gap-3 flex-wrap">
            <Link className="btn btn-accent btn-lg border-0" to="/report">Report a road problem</Link>
            <Link className="btn btn-lg border-0" to="/login">Staff login</Link>
          </div>
        </div>
      </section>
      <div className="max-w-5xl mx-auto px-5 -mt-8 grid md:grid-cols-3 gap-4">
        {[
          [Smartphone, "For citizens", "Pin a pothole or broken railing on the map, add a photo, done. No login, in English, ગુજરાતી or हिंदी. Get a ticket and confirm when it is fixed."],
          [HardHat, "For engineers", "Upload tender, work-order and completion PDFs. Pravi reads them and keeps each road's history, inspections and complaints in one timeline."],
          [Building2, "For the department", "Stop paying for repairs a contractor is already liable for, rank what needs attention, and plan the budget for the most benefit per rupee."],
        ].map(([Icon, h, p]: any) => (
          <div className="card" key={h}>
            <Icon size={22} color="var(--brand-2)" />
            <h3 className="mt-2">{h}</h3>
            <p className="m-0" style={{ color: "var(--ink-2)" }}>{p}</p>
          </div>
        ))}
      </div>
      <div className="max-w-5xl mx-auto px-5 mt-5">
        <div className="card">
          <h3>Track a complaint</h3>
          <form className="flex gap-2.5 max-w-lg" onSubmit={(e) => { e.preventDefault(); nav("/track?t=" + encodeURIComponent(t.trim())); }}>
            <input value={t} onChange={(e) => setT(e.target.value)} placeholder="Ticket number, e.g. GJ-VAD-10241" required />
            <button className="btn-primary">Track</button>
          </form>
        </div>
      </div>
      <p className="footer-note">Prototype built for the “Build for Billions” hackathon · Demo data for Vadodara district · All contractor names and figures are fictional.</p>
    </div>
  );
}
