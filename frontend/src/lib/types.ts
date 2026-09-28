export type Role = "engineer" | "ee" | "se" | "ce" | "auditor";
export const FIELD_ROLES: Role[] = ["engineer", "ee", "se", "ce"];
export const SENIOR_ROLES: Role[] = ["ee", "se", "ce"];
export type Band = "Urgent" | "This week" | "This month" | "Next season" | "Monitor";
export type Severity = "red" | "amber" | "yellow";
export type AssetType = "road_section" | "bridge" | "culvert" | "building";

export interface OfficeBrief {
  id: number; code: string; name: string; level: string; level_label: string; head: string;
  parent_id: number | null; onboarded: boolean; talukas: string[];
}
export interface Me {
  username: string; name: string; role: Role; district: string; role_label: string; rank: number;
  home: OfficeBrief; office: OfficeBrief; breadcrumb: OfficeBrief[]; offices: OfficeBrief[]; approval_limit: number | null;
}
export interface Sla {
  hours: number; due: string; state: "on_time" | "overdue" | "met" | "missed" | "na"; hours_left?: number;
  escalated_to: Role | null; escalated_label?: string | null; escalation_rank: number;
}

export interface Flag {
  key: string; severity: Severity; type: string; title: string; detail: string; action: string;
  asset_id: number; asset_code: string; asset_name: string; asset_type: AssetType;
  work_id: number | null; complaint_id: number | null; ticket: string | null; amount: number | null;
}

export interface AssetRow {
  id: number; code: string; type: AssetType; name: string; category: string; road_code: string | null;
  start_km: number | null; end_km: number | null; chainage_km: number | null; lat: number | null; lng: number | null;
  taluka: string | null; score: number; band: Band; urgent: boolean; action: string; color: string;
  under_liability: boolean; liable_contractor: string | null; liable_until: string | null;
  flags: number; red_flags: number; open_complaints: number; condition: number | null;
  geometry?: [number, number][] | null;
}

export interface Work {
  id: number; asset_id: number; road_code: string | null; start_km: number | null; end_km: number | null;
  work_type: string; work_label: string; title: string; status: string; contractor: string | null;
  estimated_cost: number | null; awarded_cost: number | null; tender_id: string | null;
  proposed_on: string | null; sanctioned_on: string | null; tendered_on: string | null; awarded_on: string | null;
  started_on: string | null; due_on: string | null; completed_on: string | null; liability_months: number | null;
  liability_end: string | null; liability_estimated: boolean; completion_period_days: number | null;
  reason: string | null; source: string; asset_name?: string; asset_code?: string;
  flags?: { severity: Severity; title: string }[];
  approver?: Role; approver_label?: string; can_approve?: boolean;
}

export interface Complaint {
  id: number; ticket: string; asset_id: number; asset_name: string | null; asset_code: string | null;
  road_code: string | null; lat: number; lng: number; km: number | null; issue_type: string; issue_label: string;
  description: string | null; language: string; report_count: number; status: string;
  liable_contractor: string | null; liable_until: string | null; liable_work_id: number | null;
  assigned_kind: string | null; assigned_to: string | null; condition: number | null;
  photo_url: string | null; fix_photo_url: string | null; reopened_count: number;
  created_at: string; verified_at: string | null; assigned_at: string | null; fixed_at: string | null; closed_at: string | null;
  sla?: Sla; source?: string; permit_id?: number | null; fix_distance_m?: number | null; office?: string | null;
  utility?: { permit_id: number; agency: string; purpose: string; to_date: string; status: string } | null;
  events?: { type: string; message: string; at: string }[];
}

export interface Liability {
  under_liability: boolean; work_id?: number; work_title?: string; contractor?: string; until?: string;
  days_left?: number; start_km?: number | null; end_km?: number | null; estimated?: boolean;
  all?: { work_id: number; contractor: string; until: string; start_km: number | null; end_km: number | null }[];
}

export interface Priority {
  score: number; band: Band; urgent: boolean; urgent_reason: string | null; action: string;
  factors: Record<string, number>; weights: Record<string, number>;
  inputs: { condition: number | null; condition_date: string | null; reports_90d: number;
    years_since_major_work: number | null; repairs_12m: number; safety_class?: string | null };
}

export interface Permit {
  id: number; asset_id: number; asset_name: string | null; road_code: string | null; start_km: number | null; end_km: number | null;
  agency: string; purpose: string; length_m: number | null; from_date: string; to_date: string; emergency: boolean;
  status: "applied" | "approved" | "rejected" | "restored"; restoration_charge: number | null; decision_note: string | null;
  decided_by: string | null; restored_on: string | null; created_by: string | null; created_at: string;
  overdue_days: number; utility_liable_until: string | null;
}
