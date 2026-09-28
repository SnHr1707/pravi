import type { AssetType, Band } from "./types";

export function inr(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  if (n === 0) return "₹0";
  if (Math.abs(n) >= 1e7) return "₹" + (n / 1e7).toFixed(2) + " cr";
  if (Math.abs(n) >= 1e5) return "₹" + (n / 1e5).toFixed(1) + " lakh";
  return "₹" + n.toLocaleString("en-IN");
}
export const num = (n: number | null | undefined) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("en-IN"));

export function fdate(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s.length <= 10 ? s + "T00:00:00" : s);
  return d.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });
}
export function fdt(s: string | null | undefined): string {
  if (!s) return "—";
  const d = new Date(s);
  return fdate(s) + ", " + d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });
}
export function daysAgo(s: string): string {
  const d = Math.round((Date.now() - new Date(s).getTime()) / 864e5);
  return d <= 0 ? "today" : d === 1 ? "1 day ago" : `${d} days ago`;
}

export const BAND_COLOR: Record<Band, string> = {
  Urgent: "#b42318", "This week": "#d92d20", "This month": "#f79009", "Next season": "#eaaa08", Monitor: "#12b76a",
};
export const TYPE_LABEL: Record<AssetType, string> = {
  road_section: "Road section", bridge: "Bridge", culvert: "Culvert", building: "Building",
};
export { STAGE_TEXT as STATUS_LABEL } from "./labels";
export const WORK_TYPES: Record<string, string> = {
  repair: "Repair / special repair", recarpet: "Re-carpeting / resurfacing", widening: "Widening",
  new_construction: "New construction", rehab: "Strengthening / rehabilitation", waterproofing: "Waterproofing",
  structural_repair: "Structural repair",
};
export const STAGES = ["proposed", "sanctioned", "tendered", "awarded", "under_construction", "completed"];
