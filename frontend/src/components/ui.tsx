import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import { BAND_COLOR, inr } from "../lib/format";
import { BAND_TEXT } from "../lib/labels";
import type { Band, Flag, Severity } from "../lib/types";

export function Badge({ tone = "", children, title }: { tone?: string; children: ReactNode; title?: string }) {
  return <span className={`badge ${tone ? "b-" + tone : ""}`} title={title}>{children}</span>;
}

const BAND_TONE: Record<Band, string> = { Urgent: "red", "This week": "red", "This month": "amber", "Next season": "yellow", Monitor: "green" };
export const BandBadge = ({ band }: { band: Band }) => <Badge tone={BAND_TONE[band]}>{BAND_TEXT[band]}</Badge>;

const SEV: Record<Severity, [string, string]> = { red: ["red", "Urgent"], amber: ["amber", "Important"], yellow: ["yellow", "For info"] };
export const SevBadge = ({ sev }: { sev: Severity }) => <Badge tone={SEV[sev][0]}>{SEV[sev][1]}</Badge>;

const C_STATUS: Record<string, [string, string]> = {
  open: ["New", "amber"], verified: ["Checked", "blue"], assigned: ["Repair in progress", "blue"],
  fixed: ["Repaired — waiting for citizen", "green"], closed: ["Closed", "green"], rejected: ["Rejected", ""],
};
export const ComplaintStatus = ({ s }: { s: string }) => {
  const [l, t] = C_STATUS[s] || [s, ""];
  return <Badge tone={t}>{l}</Badge>;
};

export function ScoreBox({ score, band, size = 42 }: { score: number; band: Band; size?: number }) {
  return (
    <div className="score" style={{ background: BAND_COLOR[band], minWidth: size, height: size, fontSize: size > 50 ? 24 : 15 }}>
      {score}
    </div>
  );
}

export function Kpi({ value, label, tone = "" }: { value: ReactNode; label: string; tone?: string }) {
  return <div className={`kpi ${tone}`}><div className="v">{value}</div><div className="l">{label}</div></div>;
}

export function Alert({ tone, children }: { tone: "red" | "amber" | "green" | "blue"; children: ReactNode }) {
  return <div className={`alert alert-${tone}`}>{children}</div>;
}

export function FlagCard({ f, showAsset = true }: { f: Flag; showAsset?: boolean }) {
  return (
    <div className={`flag ${f.severity}`}>
      <div className="t">
        {f.title} {f.amount ? <Badge tone={f.severity === "red" ? "red" : ""}>{inr(f.amount)}</Badge> : null}
      </div>
      {showAsset && (
        <div className="small"><Link to={`/app/assets/${f.asset_id}`}>{f.asset_code} · {f.asset_name}</Link></div>
      )}
      <div className="d">{f.detail}</div>
      <div className="a">→ {f.action}</div>
    </div>
  );
}

export function Modal({ title, onClose, children, wide }: { title: ReactNode; onClose: () => void; children: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const k = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, [onClose]);
  return (
    <div className="modal-bg" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" style={wide ? { width: "min(820px, 100%)" } : undefined}>
        <div className="flex items-start justify-between gap-3 mb-2">
          <h2 className="m-0">{title}</h2>
          <button className="btn-sm" onClick={onClose} aria-label="Close"><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Loading({ label = "Loading…" }: { label?: string }) {
  return <div className="card muted">{label}</div>;
}
export function ErrorBox({ error }: { error: unknown }) {
  return <Alert tone="red">{error instanceof Error ? error.message : String(error)}</Alert>;
}

// ---- toasts
const ToastCtx = createContext<(msg: string) => void>(() => {});
export function ToastProvider({ children }: { children: ReactNode }) {
  const [msg, setMsg] = useState<string | null>(null);
  const show = useCallback((m: string) => {
    setMsg(m);
    window.setTimeout(() => setMsg((cur) => (cur === m ? null : cur)), 2800);
  }, []);
  return (
    <ToastCtx.Provider value={show}>
      {children}
      {msg && <div className="toast">{msg}</div>}
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);
