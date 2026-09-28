import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Building2, FileUp, HardHat, House, IndianRupee, LogOut, MessageSquareWarning, Settings, Users } from "lucide-react";
import { api, ApiError } from "../lib/api";
import type { Me, Role } from "../lib/types";

export function useMe() {
  return useQuery<Me>({ queryKey: ["me"], queryFn: () => api<Me>("/api/auth/me"), retry: false, staleTime: 60_000 });
}

/** Renders children only for the given roles. */
export function Can({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { data } = useMe();
  return data && roles.includes(data.role) ? <>{children}</> : null;
}

const ROLE_LABEL: Record<Role, string> = { engineer: "Deputy Engineer", ee: "Executive Engineer", auditor: "Auditor (view only)" };

export default function StaffLayout() {
  const me = useMe();
  const loc = useLocation();
  const nav = useNavigate();
  const qc = useQueryClient();
  const dash = useQuery<any>({ queryKey: ["dashboard"], queryFn: () => api("/api/dashboard"), enabled: !!me.data });

  if (me.isLoading) return <div className="page muted">Loading…</div>;
  if (me.error instanceof ApiError && me.error.status === 401) {
    return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  }
  if (!me.data) return <div className="page muted">Could not reach the server.</div>;
  const k = dash.data?.kpis;
  const role = me.data.role;

  const logout = async () => {
    await api("/api/auth/logout", { method: "POST" });
    qc.clear();
    nav("/login");
  };
  const Item = ({ to, icon: Icon, label, count }: { to: string; icon: any; label: string; count?: number }) => (
    <NavLink to={to} className={({ isActive }) => `nav ${isActive ? "active" : ""}`}>
      <Icon size={18} /><span className="lbl">{label}</span>{count ? <span className="count">{count}</span> : null}
    </NavLink>
  );
  return (
    <div className="shell">
      <aside className="side">
        <NavLink className="logo" to="/app/dashboard">
          <span className="mark">P</span><span>Pravi<small>R&amp;B Asset Tracker · {me.data.district}</small></span>
        </NavLink>
        <Item to="/app/dashboard" icon={House} label="Home" />
        <Item to="/app/complaints" icon={MessageSquareWarning} label="Complaints" count={k ? k.new_complaints + k.to_assign : undefined} />
        <Item to="/app/assets" icon={Building2} label="Roads & buildings" />
        <Item to="/app/works" icon={HardHat} label="Works & tenders" />
        <Item to="/app/documents" icon={FileUp} label="Upload documents" count={k?.docs_to_review || undefined} />
        {role !== "engineer" && <Item to="/app/planner" icon={IndianRupee} label="Budget plan" />}
        <div className="sec">More</div>
        <Item to="/app/contractors" icon={Users} label="Contractors" />
        <Item to="/app/settings" icon={Settings} label="Settings" />
        <div className="me">
          <div className="n">{me.data.name.split(" (")[0]}</div>
          <div className="r">{ROLE_LABEL[role]}</div>
          <button className="btn-sm" onClick={logout}><LogOut size={14} /> <span className="lbl">Log out</span></button>
        </div>
      </aside>
      <main className="page"><Outlet /></main>
    </div>
  );
}
