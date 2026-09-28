// Plain-language labels shown to non-technical users (backend keeps its own keys).
import type { Band } from "./types";

export const BAND_TEXT: Record<Band, string> = {
  Urgent: "Urgent — safety",
  "This week": "Fix this week",
  "This month": "Fix this month",
  "Next season": "Plan for next season",
  Monitor: "OK — keep watching",
};

export const STAGE_TEXT: Record<string, string> = {
  proposed: "Proposed", sanctioned: "Approved", tendered: "Tender out", awarded: "Contract given",
  under_construction: "Work in progress", completed: "Completed", cancelled: "Cancelled",
};

export const ISSUE_ICON: Record<string, string> = {
  pothole: "🕳️", crack: "🧱", waterlogging: "🌊", signage: "🚸", railing: "🚧", leakage: "💧", other: "✏️",
};
