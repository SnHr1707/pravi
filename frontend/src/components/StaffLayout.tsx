import { useQuery, useQueryClient } from "@tanstack/react-query";
import { NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Building2, Construction, FileUp, HardHat, House, IndianRupee, LogOut, MessageSquareWarning, Network, Settings, Users } from "lucide-react";
import { api, ApiError, setViewOffice } from "../lib/api";
import type { Me, Role } from "../lib/types";
import OfficePicker from "./OfficePicker";

export function useMe() {
  return useQuery<Me>({ queryKey: ["me"], queryFn: () => api<Me>("/api/auth/me"), retry: false, staleTime: 60_000 });
}

/** Renders children only for the given roles. */
export function Can({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { data } = useMe();
  return data && roles.includes(data.role) ? <>{children}</> : null;
}

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
  const senior = role !== "engineer";

  const logout = async () => {
    await api("/api/auth/logout", { method: "POST" });
    setViewOffice(null);
    qc.clear();
    nav("/login");
  };
  const switchOffice = (id: string) => {
    setViewOffice(Number(id) === me.data!.home.id ? null : Number(id));
    qc.invalidateQueries();
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
          <span className="mark">P</span><span>Pravi<small>R&amp;B Asset Tracker · Gujarat</small></span>
        </NavLink>
        <OfficePicker me={me.data} onPick={(o) => switchOffice(String(o.id))} />
        <Item to="/app/dashboard" icon={House} label="Home" />
        <Item to="/app/complaints" icon={MessageSquareWarning} label="Complaints" count={k ? k.new_complaints + k.to_assign : undefined} />
        <Item to="/app/assets" icon={Building2} label="Roads & buildings" />
        <Item to="/app/works" icon={HardHat} label="Works & tenders" count={k?.awaiting_my_approval || undefined} />
        <Item to="/app/documents" icon={FileUp} label="Upload documents" count={k?.docs_to_review || undefined} />
        <Item to="/app/digging" icon={Construction} label="Road digging" count={(k?.permits_to_decide || 0) + (k?.roads_not_restored || 0) || undefined} />
        {senior && <Item to="/app/planner" icon={IndianRupee} label="Budget plan" />}
        <div className="sec">More</div>
        {senior && <Item to="/app/offices" icon={Network} label="Offices" />}
        <Item to="/app/contractors" icon={Users} label="Contractors" />
        <Item to="/app/settings" icon={Settings} label="Settings" />
        <div className="me">
          <div className="n">{me.data.name.split(" (")[0]}</div>
          <div className="r">{me.data.role_label}<br />{me.data.home.name}</div>
          <button className="btn-sm" onClick={logout}><LogOut size={14} /> <span className="lbl">Log out</span></button>
        </div>
      </aside>
      <main className="page"><Outlet /></main>
    </div>
  );
}
