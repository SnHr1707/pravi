"""The brain: liability lookup, risk flags and the priority score.

Everything is computed from the stored records, so the rules stay transparent
and the numbers can always be traced back to a document, inspection or complaint.
"""
import calendar
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from sqlmodel import Session, select

from .models import Asset, Complaint, DigPermit, Inspection, Setting, Work

MAJOR_WORKS = {"new_construction", "recarpet", "rehab", "widening", "reconstruction", "structural_repair"}
REPAIR_WORKS = {"repair", "recarpet", "rehab", "waterproofing", "structural_repair"}
SCOPE_CHANGE_WORKS = {"widening", "new_construction"}
EXPECTED_LIFE = {"road_section": 7, "bridge": 25, "culvert": 15, "building": 20}
ROAD_CRIT = {"SH": 1.0, "MDR": 0.7, "ODR": 0.5, "VR": 0.3}
BUILDING_CRIT = {"hospital": 1.0, "school": 0.8, "office": 0.6, "quarters": 0.4}
DEFAULT_WEIGHTS = {"condition": 0.30, "criticality": 0.25, "complaints": 0.20, "age": 0.15, "repeat": 0.10}
ACTIVE_COMPLAINT = {"open", "verified", "assigned", "fixed"}
WORK_LABEL = {
    "new_construction": "New construction", "widening": "Widening", "recarpet": "Re-carpeting",
    "repair": "Repair", "rehab": "Rehabilitation", "waterproofing": "Waterproofing",
    "structural_repair": "Structural repair", "reconstruction": "Reconstruction",
}


def add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def lakh(rupees: Optional[float]) -> str:
    if not rupees:
        return "₹0"
    if rupees >= 1e7:
        return f"₹{rupees / 1e7:.2f} crore"
    return f"₹{rupees / 1e5:.1f} lakh"


def work_ref_date(w: Work) -> Optional[date]:
    """The date a work entered the pipeline (used to test it against liability windows)."""
    return w.tendered_on or w.sanctioned_on or w.proposed_on or w.awarded_on or w.completed_on


def get_weights(session: Session) -> Dict[str, float]:
    s = session.get(Setting, "priority_weights")
    if s:
        try:
            w = json.loads(s.value)
            return {k: float(w.get(k, v)) for k, v in DEFAULT_WEIGHTS.items()}
        except (ValueError, TypeError):
            pass
    return dict(DEFAULT_WEIGHTS)


@dataclass
class Ctx:
    today: date
    assets: Dict[int, Asset]
    works: List[Work]
    inspections: Dict[int, List[Inspection]] = field(default_factory=dict)
    complaints: Dict[int, List[Complaint]] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=dict)
    permits: List[DigPermit] = field(default_factory=list)


def load_ctx(session: Session, district: str, today: Optional[date] = None, offices=None) -> Ctx:
    """Everything the rules need. `offices` limits the assets to one unit of the hierarchy
    (works stay district-wide so liability on a road is always judged on its full history)."""
    assets = {a.id: a for a in session.exec(select(Asset).where(Asset.district == district)).all()
              if offices is None or a.office_id in offices}
    works = [w for w in session.exec(select(Work).where(Work.district == district)).all()]
    insp = defaultdict(list)
    for i in session.exec(select(Inspection)).all():
        if i.asset_id in assets:
            insp[i.asset_id].append(i)
    for v in insp.values():
        v.sort(key=lambda i: i.inspected_on, reverse=True)
    comps = defaultdict(list)
    for c in session.exec(select(Complaint).where(Complaint.district == district)).all():
        if c.asset_id in assets:
            comps[c.asset_id].append(c)
    permits = [p for p in session.exec(select(DigPermit).where(DigPermit.district == district)).all()
               if p.asset_id in assets]
    return Ctx(today=today or date.today(), assets=assets, works=works, inspections=insp,
               complaints=comps, weights=get_weights(session), permits=permits)


# ---------------------------------------------------------------- matching

def _overlaps(a0, a1, b0, b1) -> bool:
    if a0 is None or a1 is None or b0 is None or b1 is None:
        return False
    if b0 == b1:  # a point
        return a0 <= b0 <= a1
    if a0 == a1:
        return b0 <= a0 <= b1
    return max(a0, b0) < min(a1, b1)


def _covers(a0, a1, b0, b1) -> bool:
    return None not in (a0, a1, b0, b1) and a0 <= b0 and a1 >= b1


def works_on(ctx: Ctx, asset: Asset, k0: Optional[float] = None, k1: Optional[float] = None) -> List[Work]:
    """Works touching an asset. Road works match by road code + km range, not by name."""
    if asset.asset_type == "road_section":
        s0 = asset.start_km if k0 is None else k0
        s1 = asset.end_km if k1 is None else k1
        return [w for w in ctx.works if w.road_code == asset.road_code and w.start_km is not None
                and _overlaps(w.start_km, w.end_km, s0, s1)]
    return [w for w in ctx.works if w.asset_id == asset.id]


def liability_windows(ctx: Ctx, asset: Asset, k0=None, k1=None, on: Optional[date] = None,
                      exclude_work_id: Optional[int] = None) -> List[Work]:
    """Completed works whose defect-liability window is still running on `on`
    over the given stretch, ignoring works that a later completed work has replaced."""
    on = on or ctx.today
    done = [w for w in works_on(ctx, asset, k0, k1)
            if w.id != exclude_work_id and w.status == "completed" and w.completed_on
            and w.completed_on <= on and w.liability_end]
    active = []
    for c in done:
        if c.liability_end < on:
            continue
        if asset.asset_type == "road_section":
            q0 = max(c.start_km, asset.start_km if k0 is None else k0)
            q1 = min(c.end_km, asset.end_km if k1 is None else k1)
            superseded = any(d.completed_on > c.completed_on and _covers(d.start_km, d.end_km, q0, q1)
                             for d in done if d.id != c.id)
        else:
            superseded = any(d.completed_on > c.completed_on for d in done if d.id != c.id)
        if not superseded:
            active.append(c)
    active.sort(key=lambda w: w.completed_on, reverse=True)
    return active


def liability_summary(ctx: Ctx, asset: Asset, km: Optional[float] = None, on: Optional[date] = None) -> dict:
    on = on or ctx.today
    wins = liability_windows(ctx, asset, km, km, on) if km is not None else liability_windows(ctx, asset, on=on)
    if not wins:
        return {"under_liability": False}
    w = wins[0]
    return {
        "under_liability": True,
        "work_id": w.id,
        "work_title": w.title,
        "contractor": w.contractor,
        "until": w.liability_end.isoformat(),
        "days_left": (w.liability_end - on).days,
        "start_km": w.start_km,
        "end_km": w.end_km,
        "estimated": w.liability_estimated,
        "all": [{"work_id": x.id, "contractor": x.contractor, "until": x.liability_end.isoformat(),
                 "start_km": x.start_km, "end_km": x.end_km} for x in wins],
    }


def km_label(w_or_a) -> str:
    s, e = getattr(w_or_a, "start_km", None), getattr(w_or_a, "end_km", None)
    if s is None:
        return ""
    return f"km {s:g}–{e:g}"


# ---------------------------------------------------------------- priority

def latest_condition(ctx: Ctx, asset: Asset) -> Optional[Inspection]:
    for i in ctx.inspections.get(asset.id, []):
        if i.condition and i.kind in ("inspection", "structural_audit"):
            return i
    return None


def last_of_kind(ctx: Ctx, asset: Asset, kind: str) -> Optional[Inspection]:
    for i in ctx.inspections.get(asset.id, []):
        if i.kind == kind:
            return i
    return None


def criticality(ctx: Ctx, asset: Asset) -> float:
    road_cat = asset.category if asset.asset_type == "road_section" else json.loads(asset.attrs or "{}").get("road_category")
    base = ROAD_CRIT.get(road_cat or "", 0.5)
    if asset.asset_type == "bridge":
        return min(1.0, base * 1.2)
    if asset.asset_type == "culvert":
        return base * 0.9
    if asset.asset_type == "building":
        b = BUILDING_CRIT.get(asset.category, 0.5)
        return min(1.0, b * (1.2 if asset.category == "hospital" else 1.0))
    return base


def last_major_date(ctx: Ctx, asset: Asset) -> Optional[date]:
    ds = [w.completed_on for w in works_on(ctx, asset)
          if w.status == "completed" and w.completed_on and w.work_type in MAJOR_WORKS]
    if ds:
        return max(ds)
    if asset.year_built:
        return date(asset.year_built, 1, 1)
    return None


def repairs_last_year(ctx: Ctx, asset: Asset) -> List[Work]:
    cutoff = ctx.today - timedelta(days=365)
    out = []
    for w in works_on(ctx, asset):
        if w.status == "cancelled" or w.work_type not in {"repair", "waterproofing", "structural_repair"}:
            continue
        d = w.completed_on or work_ref_date(w)
        if d and d >= cutoff:
            out.append(w)
    return out


def priority(ctx: Ctx, asset: Asset) -> dict:
    wts = ctx.weights
    insp = latest_condition(ctx, asset)
    f_cond = (5 - insp.condition) / 4 if insp else 0.5
    f_crit = criticality(ctx, asset)
    cutoff = datetime.combine(ctx.today - timedelta(days=90), datetime.min.time())
    reports = sum(c.report_count for c in ctx.complaints.get(asset.id, [])
                  if c.status != "rejected" and c.created_at >= cutoff)
    f_comp = min(1.0, reports / 10)
    lm = last_major_date(ctx, asset)
    years = (ctx.today - lm).days / 365.25 if lm else None
    f_age = min(1.0, years / EXPECTED_LIFE.get(asset.asset_type, 10)) if years is not None else 0.5
    reps = repairs_last_year(ctx, asset)
    f_rep = min(1.0, len(reps) / 3)
    factors = {"condition": f_cond, "criticality": f_crit, "complaints": f_comp, "age": f_age, "repeat": f_rep}
    score = round(100 * sum(wts[k] * factors[k] for k in factors))

    urgent, reason = False, None
    if asset.asset_type == "bridge":
        if insp and insp.condition == 1:
            urgent, reason = True, "Bridge rated 1 (critical)"
        last = last_of_kind(ctx, asset, "inspection")
        if not last or (ctx.today - last.inspected_on).days > 365:
            urgent, reason = True, "Bridge inspection overdue by 6+ months"

    audit = last_of_kind(ctx, asset, "structural_audit")
    if audit and audit.safety_class in ("C1", "C2A"):
        urgent = True
        reason = {"C1": "Structural audit class C1 — dangerous, close / evacuate",
                  "C2A": "Structural audit class C2A — major repairs, vacate while repairing"}[audit.safety_class]

    if urgent:
        band = "Urgent"
    elif score >= 80:
        band = "This week"
    elif score >= 60:
        band = "This month"
    elif score >= 40:
        band = "Next season"
    else:
        band = "Monitor"

    liab = liability_summary(ctx, asset)
    if liab["under_liability"] and band != "Monitor":
        action = f"Send repair notice to {liab['contractor']} — they must repair free"
    elif band in ("Urgent", "This week", "This month"):
        action = {"bridge": "Detailed structural inspection + repair",
                  "building": "Sanction repair after structural check",
                  "culvert": "Clean and repair culvert"}.get(asset.asset_type, "Sanction repair work")
    elif band == "Next season":
        action = "Include in next season's maintenance programme"
    else:
        action = "Routine monitoring"

    return {
        "score": score, "band": band, "urgent": urgent, "urgent_reason": reason, "action": action,
        "factors": {k: round(v, 2) for k, v in factors.items()},
        "weights": wts,
        "inputs": {
            "condition": insp.condition if insp else None,
            "condition_date": insp.inspected_on.isoformat() if insp else None,
            "reports_90d": reports,
            "years_since_major_work": round(years, 1) if years is not None else None,
            "repairs_12m": len(reps),
            "safety_class": audit.safety_class if audit else None,
        },
    }


# ---------------------------------------------------------------- flags

def _flag(key, severity, ftype, title, detail, asset, action, work=None, complaint=None, amount=None):
    return {
        "key": key, "severity": severity, "type": ftype, "title": title, "detail": detail,
        "asset_id": asset.id, "asset_code": asset.code, "asset_name": asset.name,
        "asset_type": asset.asset_type, "work_id": work.id if work else None,
        "complaint_id": complaint.id if complaint else None,
        "ticket": complaint.ticket if complaint else None,
        "amount": amount, "action": action,
    }


SAFETY_CLASS = {"C1": "dangerous — close / evacuate now", "C2A": "major repairs needed, vacate while repairing",
                "C2B": "major repairs needed, can stay in use", "C3": "minor repairs"}
SAFETY_ACTION = {"C1": "Close the structure to the public today and plan demolition / reconstruction",
                 "C2A": "Vacate and sanction structural repairs", "C2B": "Sanction structural repairs",
                 "C3": "Routine repairs"}


def compute_flags(ctx: Ctx) -> List[dict]:
    flags: List[dict] = []
    t = ctx.today

    # 1. Paid work on a stretch still under a contractor's defect liability
    for w in ctx.works:
        if w.status == "cancelled" or w.work_type not in (REPAIR_WORKS | SCOPE_CHANGE_WORKS):
            continue
        asset = ctx.assets.get(w.asset_id)
        ref = work_ref_date(w)
        if not asset or not ref:
            continue
        if asset.asset_type == "road_section":
            wins = liability_windows(ctx, asset, w.start_km, w.end_km, on=ref, exclude_work_id=w.id)
        else:
            wins = liability_windows(ctx, asset, on=ref, exclude_work_id=w.id)
        wins = [p for p in wins if p.completed_on and p.completed_on < ref]
        if not wins:
            continue
        p = wins[0]
        cost = w.awarded_cost or w.estimated_cost
        where = f"{w.road_code} {km_label(w)}" if w.road_code else asset.name
        if w.work_type in SCOPE_CHANGE_WORKS:
            flags.append(_flag(
                f"liab-review-{w.id}", "amber", "scope_change_in_liability",
                "New work planned on a road still under guarantee — please check",
                f"{where} is under liability with {p.contractor} until {p.liability_end:%d %b %Y}. "
                f"A change of scope may be legitimate, but check it does not hide defect repairs.",
                asset, "Engineer to confirm scope is new work, not defect repair", work=w, amount=cost))
        else:
            flags.append(_flag(
                f"liab-paid-{w.id}", "red", "paid_repair_in_liability",
                "Paying for a repair the contractor must do for free",
                f"{where}: '{w.title}' ({w.status}, {lakh(cost)}) dated {ref:%d %b %Y}. "
                f"{WORK_LABEL.get(p.work_type, p.work_type)} of this stretch was done by {p.contractor}, "
                f"completed {p.completed_on:%d %b %Y}; under Clause 17-A they must fix defects free until {p.liability_end:%d %b %Y}.",
                asset, f"Stop this payment and send a repair notice to {p.contractor}", work=w, amount=cost))

    for asset in ctx.assets.values():
        comps = ctx.complaints.get(asset.id, [])
        # 2. Repeat failure
        reps = repairs_last_year(ctx, asset)
        verified = [c for c in comps if c.status in {"verified", "assigned", "fixed", "closed"}
                    and c.created_at.date() >= t - timedelta(days=365)]
        if len(reps) >= 3:
            spent = sum((r.awarded_cost or r.estimated_cost or 0) for r in reps)
            flags.append(_flag(
                f"repeat-{asset.id}", "red", "repeat_failure", f"Repaired {len(reps)} times in 12 months",
                f"{asset.name}: {len(reps)} repairs costing {lakh(spent)} in the last year. Patching is not holding.",
                asset, "Investigate root cause; consider full re-carpeting / rehabilitation", amount=spent))
        elif len(verified) >= 4:
            flags.append(_flag(
                f"recurring-{asset.id}", "amber", "recurring_complaints",
                f"{len(verified)} verified complaints in 12 months",
                f"{asset.name} keeps failing. Check drainage and pavement condition.",
                asset, "Schedule detailed inspection"))

        # 7. Ageing road
        if asset.asset_type == "road_section":
            lm = last_major_date(ctx, asset)
            in_pipeline = any(w.work_type in MAJOR_WORKS and w.status not in ("completed", "cancelled")
                              for w in works_on(ctx, asset))
            if lm and (t - lm).days > 7 * 365 and not in_pipeline:
                yrs = (t - lm).days / 365.25
                flags.append(_flag(
                    f"ageing-{asset.id}", "yellow", "ageing_asset", f"Not resurfaced for {yrs:.0f} years",
                    f"{asset.name}: last renewal {lm:%b %Y}. Bituminous surfaces typically need renewal every 5–7 years.",
                    asset, "Plan re-carpeting before failure"))

        # 8. Bridge inspections
        if asset.asset_type == "bridge":
            last = last_of_kind(ctx, asset, "inspection")
            days = (t - last.inspected_on).days if last else None
            if days is None or days > 183:
                sev = "red" if (days is None or days > 365) else "amber"
                flags.append(_flag(
                    f"bridge-insp-{asset.id}", sev, "inspection_overdue",
                    "Bridge inspection overdue",
                    f"{asset.name}: last inspected {'never' if not last else last.inspected_on.strftime('%d %b %Y')}"
                    f"{'' if days is None else f' ({days // 30} months ago)'}. Bridges need pre- and post-monsoon inspection.",
                    asset, "Inspect this bridge now"))
            if last and last.condition and last.condition <= 2:
                acted = any((w.started_on or w.awarded_on or w.tendered_on or w.sanctioned_on or date.min) >= last.inspected_on
                            for w in works_on(ctx, asset) if w.status != "cancelled")
                if not acted:
                    flags.append(_flag(
                        f"bridge-poor-{asset.id}", "red", "poor_condition_no_action",
                        f"Bridge rated {last.condition}/5 with no action",
                        f"{asset.name} was rated {last.condition}/5 on {last.inspected_on:%d %b %Y}; no repair work sanctioned since.",
                        asset, "Sanction structural repair; consider load restriction"))

        # 9. Culverts: pre-monsoon cleaning
        if asset.asset_type == "culvert":
            season_end = date(t.year, 6, 15)
            season_start = date(t.year, 3, 1)
            if t < season_end:
                season_end, season_start = date(t.year - 1, 6, 15), date(t.year - 1, 3, 1)
            last = last_of_kind(ctx, asset, "cleaning")
            if not last or not (season_start <= last.inspected_on <= season_end):
                wl = [c for c in comps if c.issue_type == "waterlogging" and c.status != "rejected"]
                flags.append(_flag(
                    f"culvert-{asset.id}", "red" if wl else "amber", "missed_monsoon_cleaning",
                    "Missed pre-monsoon cleaning" + (" + waterlogging reported" if wl else ""),
                    f"{asset.name}: last cleaned {'never' if not last else last.inspected_on.strftime('%d %b %Y')}. "
                    f"Blocked culverts send water into the road and destroy it.",
                    asset, "Clean culvert and inspect adjacent pavement"))

        # 10. Buildings: structural audit
        if asset.asset_type == "building":
            last = last_of_kind(ctx, asset, "structural_audit")
            age = t.year - (asset.year_built or t.year)
            if age > 15 and (not last or (t - last.inspected_on).days > 5 * 365):
                flags.append(_flag(
                    f"audit-{asset.id}", "red" if asset.category == "hospital" else "amber", "audit_overdue",
                    "Structural audit overdue",
                    f"{asset.name} ({age} years old): last structural audit "
                    f"{'never' if not last else last.inspected_on.strftime('%b %Y')}. Audits are due every 5 years for buildings over 15 years old.",
                    asset, "Commission structural audit"))

        # 11. Structural safety class (Mumbai-style C1 / C2A / C2B / C3)
        if asset.asset_type in ("building", "bridge"):
            audit = last_of_kind(ctx, asset, "structural_audit")
            if audit and audit.safety_class in SAFETY_CLASS and audit.safety_class != "C3":
                acted = any((w.started_on or w.awarded_on or w.tendered_on or w.sanctioned_on or date.min) >= audit.inspected_on
                            for w in works_on(ctx, asset) if w.status != "cancelled")
                if not acted or audit.safety_class == "C1":
                    sev = "amber" if audit.safety_class == "C2B" else "red"
                    flags.append(_flag(
                        f"safety-{asset.id}", sev, "structural_danger",
                        f"Structural class {audit.safety_class}: {SAFETY_CLASS[audit.safety_class]}",
                        f"{asset.name}: audit of {audit.inspected_on:%d %b %Y} placed it in class {audit.safety_class}"
                        + ("" if acted else "; no repair work sanctioned since") + ".",
                        asset, SAFETY_ACTION[audit.safety_class]))

        # complaint-level flags
        for c in comps:
            if c.status == "assigned" and c.assigned_kind == "contractor" and c.assigned_at \
                    and (t - c.assigned_at.date()).days > 14:
                flags.append(_flag(
                    f"noncomp-{c.id}", "red", "contractor_non_compliance",
                    f"{c.assigned_to} has not fixed a defect in {(t - c.assigned_at.date()).days} days",
                    f"Ticket {c.ticket} ({c.issue_type}, {c.report_count} reports) was sent to the liable contractor "
                    f"on {c.assigned_at:%d %b %Y} and is still open.",
                    asset, "Escalate: recover cost from performance security if not fixed", complaint=c))
            elif c.status in ("verified", "assigned") and c.assigned_kind != "contractor":
                since = (c.assigned_at or c.verified_at or c.created_at).date()
                if (t - since).days > 7:
                    flags.append(_flag(
                        f"stale-{c.id}", "amber", "stale_complaint",
                        f"Complaint unresolved for {(t - since).days} days",
                        f"Ticket {c.ticket} ({c.issue_type}, {c.report_count} reports) verified but not fixed.",
                        asset, "Assign and fix", complaint=c))

    # 12. Road cut by a utility and not restored
    for p in ctx.permits:
        asset = ctx.assets.get(p.asset_id)
        if asset and p.status == "approved" and p.to_date < t:
            flags.append(_flag(
                f"dig-{p.id}", "red" if (t - p.to_date).days > 15 else "amber", "dig_not_restored",
                f"{p.agency} dug the road and has not restored it",
                f"Permit #{p.id}: {asset.road_code or asset.name} {('km %g–%g' % (p.start_km, p.end_km)) if p.start_km is not None else ''} "
                f"for {p.purpose or 'utility work'}; digging window ended {p.to_date:%d %b %Y} ({(t - p.to_date).days} days ago).",
                asset, f"Get {p.agency} to restore the road, or restore it and recover the restoration charge",
                amount=p.restoration_charge))

    # 3. Delayed works  /  6. Liability expiring soon
    for w in ctx.works:
        asset = ctx.assets.get(w.asset_id)
        if not asset:
            continue
        if w.status in ("awarded", "under_construction") and w.due_on and w.due_on < t:
            flags.append(_flag(
                f"delay-{w.id}", "amber", "delayed_work", f"Work running {(t - w.due_on).days} days late",
                f"'{w.title}' by {w.contractor or 'contractor'} was due {w.due_on:%d %b %Y}.",
                asset, "Review progress; apply delay penalty clause", work=w, amount=w.awarded_cost))
        if w.status == "completed" and w.liability_end and 0 <= (w.liability_end - t).days <= 60:
            flags.append(_flag(
                f"expiring-{w.id}", "amber", "liability_expiring",
                f"Guarantee ends in {(w.liability_end - t).days} days — inspect now",
                f"{w.contractor}'s liability for '{w.title}' ends {w.liability_end:%d %b %Y}. "
                f"Last chance to get defects fixed free.",
                asset, "Inspect now and log every defect before expiry", work=w))

    order = {"red": 0, "amber": 1, "yellow": 2}
    flags.sort(key=lambda f: (order[f["severity"]], -(f["amount"] or 0)))
    return flags


def money_at_risk(flags: List[dict]) -> float:
    return sum(f["amount"] or 0 for f in flags if f["type"] == "paid_repair_in_liability")


def contractor_scorecard(ctx: Ctx) -> List[dict]:
    rows: Dict[str, dict] = {}
    today = ctx.today
    for w in ctx.works:
        if not w.contractor or w.asset_id not in ctx.assets:
            continue
        r = rows.setdefault(w.contractor, {"contractor": w.contractor, "works": 0, "value": 0.0,
                                           "active_liabilities": 0, "defects_in_liability": 0,
                                           "defects_open": 0, "overdue_notices": 0, "delayed_works": 0,
                                           "fix_days": []})
        r["works"] += 1
        r["value"] += w.awarded_cost or w.estimated_cost or 0
        if w.status == "completed" and w.liability_end and w.liability_end >= today:
            r["active_liabilities"] += 1
        if w.status in ("awarded", "under_construction") and w.due_on and w.due_on < today:
            r["delayed_works"] += 1
    for comps in ctx.complaints.values():
        for c in comps:
            if not c.liable_contractor or c.status == "rejected":
                continue
            r = rows.get(c.liable_contractor)
            if not r:
                continue
            r["defects_in_liability"] += 1
            if c.status in ("open", "verified", "assigned"):
                r["defects_open"] += 1
                if c.assigned_kind == "contractor" and c.assigned_at and (today - c.assigned_at.date()).days > 14:
                    r["overdue_notices"] += 1
            if c.fixed_at and c.assigned_at and c.assigned_kind == "contractor":
                r["fix_days"].append((c.fixed_at - c.assigned_at).days)
    out = []
    for r in rows.values():
        fd = r.pop("fix_days")
        r["avg_fix_days"] = round(sum(fd) / len(fd), 1) if fd else None
        if r["overdue_notices"] or r["delayed_works"]:
            r["risk"] = "high"
        elif r["defects_open"]:
            r["risk"] = "medium"
        else:
            r["risk"] = "low"
        out.append(r)
    out.sort(key=lambda r: (-r["overdue_notices"], -r["defects_open"], -r["value"]))
    return out
