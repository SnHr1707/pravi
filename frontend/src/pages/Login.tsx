import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/api";
import { Alert } from "../components/ui";

export default function Login() {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const [sp] = useSearchParams();
  const qc = useQueryClient();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      await api("/api/auth/login", { json: { username: u, password: p } });
      await qc.invalidateQueries();
      const next = sp.get("next");
      nav(next && next.startsWith("/app") ? next : "/app/dashboard");
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="min-h-screen grid place-items-center p-5" style={{ background: "linear-gradient(160deg,#1d3a6e,#2f5ea8)" }}>
      <div className="w-full max-w-sm">
        <div className="card">
          <Link to="/" className="flex items-center gap-2.5 font-extrabold text-[17px] mb-3.5" style={{ color: "var(--ink)" }}>
            <span className="w-8 h-8 rounded-lg grid place-items-center text-white" style={{ background: "var(--accent)" }}>P</span> Pravi · Staff login
          </Link>
          <form onSubmit={submit}>
            <label>Username</label><input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" required />
            <label>Password</label><input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" required />
            {err && <Alert tone="red">{err}</Alert>}
            <button className="btn-primary w-full mt-3.5" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
          </form>
        </div>
      </div>
    </div>
  );
}
