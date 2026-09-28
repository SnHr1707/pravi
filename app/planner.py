"""Budget planner: where does each rupee do the most good?

Order of funding
  1. Free fixes      – defects on assets still under contractor liability (₹0)
  2. Safety first    – urgent bridges and critical buildings in poor condition
  3. Value per rupee – everything else, ranked by people-benefit ÷ cost,
                       with a reserved share for rural roads (ODR / village roads)

All rates and multipliers are illustrative assumptions and can be changed here.
"""
import json
from typing import List, Optional

from .rules import (MAJOR_WORKS, Ctx, compute_flags, criticality, lakh, latest_condition, liability_summary,
                    priority, works_on)

# Illustrative unit rates (₹ per km) for re-carpeting, by road category
RECARPET_PER_KM = {"SH": 14e5, "MDR": 10e5, "ODR": 6e5, "VR": 4e5}
RECONSTRUCT_FACTOR = 3.0      # a failed road (condition 1) needs reconstruction ≈ 3× re-carpeting
EARLY_ACTION_BONUS = 1.5      # fixing at condition 2–3 prevents a far costlier rebuild later
FAILURE_PROB = 0.5            # chance an ageing road at condition 2–3 fails before the next cycle if left alone
BRIDGE_REHAB = 1.2e7
CULVERT_FIX = 2.5e5
BUILDING_RATE_SQM = 1800
BUILDING_USERS = {"hospital": 1500, "school": 800, "office": 400, "quarters": 90}
RURAL = {"ODR", "VR"}


def _attrs(a):
    try:
        return json.loads(a.attrs or "{}")
    except ValueError:
        return {}


def _road_traffic(ctx: Ctx, asset) -> int:
    for a in ctx.assets.values():
        if a.asset_type == "road_section" and a.road_code == asset.road_code:
            return int(_attrs(a).get("traffic_pcu_day", 1000))
    return 1000


def _road_category(asset) -> Optional[str]:
    if asset.asset_type == "road_section":
        return asset.category
    return _attrs(asset).get("road_category")


def build_candidates(ctx: Ctx) -> List[dict]:
    flags = compute_flags(ctx)
    blocked_work_ids = {f["work_id"] for f in flags if f["type"] == "paid_repair_in_liability"}
    flag_types_by_asset = {}
    for f in flags:
        flag_types_by_asset.setdefault(f["asset_id"], set()).add(f["type"])

    cands = []
    # money that should not be spent: paid works on stretches still under contractor liability
    for f in flags:
        if f["type"] != "paid_repair_in_liability":
            continue
        w = next((x for x in ctx.works if x.id == f["work_id"]), None)
        if not w or w.status in ("completed", "cancelled"):
            continue
        a = ctx.assets[w.asset_id]
        cands.append({"asset_id": a.id, "asset_code": a.code, "asset_name": a.name, "asset_type": a.asset_type,
                      "road_category": _road_category(a), "rural": _road_category(a) in RURAL, "condition": None,
                      "daily_users": 0, "priority": None, "band": None, "urgent": False, "kind": "blocked",
                      "work_id": w.id, "cost": w.awarded_cost or w.estimated_cost or 0,
                      "title": f"{w.title} ({w.status})", "source": "flag", "avoided": 0.0, "value": None})

    for a in ctx.assets.values():
        pr = priority(ctx, a)
        insp = latest_condition(ctx, a)
        cond = insp.condition if insp else 3
        at = _attrs(a)
        cat = _road_category(a)
        rural = cat in RURAL
        ftypes = flag_types_by_asset.get(a.id, set())
        need = min(1.0, (5 - cond) / 4 + 0.3 * pr["factors"]["complaints"])
        if a.asset_type == "culvert":
            need = 0.7 if "missed_monsoon_cleaning" in ftypes else 0.2
        # skip assets where a major work is already running
        if any(w.status in ("tendered", "awarded", "under_construction") and w.work_type in MAJOR_WORKS
               for w in works_on(ctx, a)):
            continue
        # roads at condition 3 only qualify for early action once they are ageing
        yrs = pr["inputs"]["years_since_major_work"]
        if a.asset_type == "road_section" and cond == 3 and (yrs is None or yrs < 5):
            need = min(need, 0.4)
        if need < 0.45 and pr["band"] in ("Monitor",):
            continue

        # people served per day
        if a.asset_type == "road_section":
            users = int(at.get("traffic_pcu_day", 1000))
            span = (a.end_km or 0) - (a.start_km or 0)
        elif a.asset_type in ("bridge", "culvert"):
            users = _road_traffic(ctx, a)
            span = 5.0 if a.asset_type == "bridge" else 1.0  # a failed bridge cuts the whole route
        else:
            users = int(at.get("daily_users", BUILDING_USERS.get(a.category, 300)))
            span = 1.0

        liab = liability_summary(ctx, a)
        base = {"asset_id": a.id, "asset_code": a.code, "asset_name": a.name, "asset_type": a.asset_type,
                "road_category": cat, "rural": rural, "condition": insp.condition if insp else None, "daily_users": users,
                "priority": pr["score"], "band": pr["band"], "urgent": pr["urgent"]}

        # 1. free fix under liability
        if liab["under_liability"] and cond <= 3:
            cands.append({**base, "kind": "free", "work_id": None, "cost": 0.0,
                          "title": f"Defect notice to {liab['contractor']} (liable until {liab['until']})",
                          "source": "liability", "avoided": 0.0, "value": None})
            continue

        # existing proposal/sanction on this asset?
        prop = [w for w in works_on(ctx, a) if w.status in ("proposed", "sanctioned") and w.asset_id == a.id
                and w.id not in blocked_work_ids and w.work_type in (MAJOR_WORKS | {"repair", "waterproofing"})]

        if prop:
            w = prop[0]
            cost = w.estimated_cost or 0
            title, source = w.title, "proposal"
        else:
            if need < 0.45:
                continue
            if a.asset_type == "road_section":
                rate = RECARPET_PER_KM.get(a.category, 8e5)
                if cond <= 1:
                    cost, title = rate * span * RECONSTRUCT_FACTOR, f"Reconstruction of {a.road_code} km {a.start_km:g}–{a.end_km:g}"
                else:
                    cost, title = rate * span, f"Re-carpeting of {a.road_code} km {a.start_km:g}–{a.end_km:g}"
            elif a.asset_type == "bridge":
                cost, title = BRIDGE_REHAB, f"Rehabilitation of {a.name}"
            elif a.asset_type == "culvert":
                cost, title = CULVERT_FIX, f"Clean and repair {a.name}"
            else:
                area = at.get("floor_area_sqm", 2000)
                cost, title = area * BUILDING_RATE_SQM, f"Structural repair and waterproofing, {a.name}"
            source = "suggested"
        if cost <= 0:
            continue
        early = a.asset_type == "road_section" and 2 <= cond <= 3
        crit = criticality(ctx, a)
        benefit = users * need * crit * max(span, 1.0) * (EARLY_ACTION_BONUS if early else 1.0)
        avoided = cost * (RECONSTRUCT_FACTOR - 1) * FAILURE_PROB if (early and a.asset_type == "road_section") else 0.0
        kind = "safety" if (pr["urgent"] or (a.asset_type == "building" and a.category == "hospital" and cond <= 2)
                            or (a.asset_type == "bridge" and cond <= 2)) else "value"
        cands.append({**base, "kind": kind, "work_id": prop[0].id if prop else None, "cost": round(cost),
                      "title": title, "source": source, "benefit": round(benefit), "avoided": round(avoided),
                      "early": early, "need": round(need, 2), "criticality": round(crit, 2),
                      "value": round(benefit / (cost / 1e7), 1)})  # benefit points per ₹1 crore
    return cands


def plan(ctx: Ctx, budget: float, rural_share: float = 0.25) -> dict:
    cands = build_candidates(ctx)
    funded, deferred, free, blocked = [], [], [], []
    left = budget

    for c in cands:
        if c["kind"] == "free":
            c["reason"] = "Free: contractor is liable — costs the department ₹0"
            free.append(c)
        elif c["kind"] == "blocked":
            c["reason"] = "Blocked: this stretch is under contractor liability — do not pay for it"
            blocked.append(c)

    for c in sorted([c for c in cands if c["kind"] == "safety"], key=lambda c: -c["priority"]):
        if c["cost"] <= left:
            left -= c["cost"]
            c["reason"] = "Safety first: " + ("urgent bridge" if c["asset_type"] == "bridge" else "critical asset in poor condition")
            funded.append(c)
        else:
            c["reason"] = f"Safety-critical but needs {lakh(c['cost'])} more than remains — seek additional funds"
            deferred.append(c)

    value = [c for c in cands if c["kind"] == "value"]
    rural_pool = sorted([c for c in value if c["rural"]], key=lambda c: -c["value"])
    main_pool = sorted([c for c in value if not c["rural"]], key=lambda c: -c["value"])
    rural_budget = left * rural_share
    main_budget = left - rural_budget

    def fill(pool, money, label):
        rest = []
        for c in pool:
            if c["cost"] <= money:
                money -= c["cost"]
                c["reason"] = label
                funded.append(c)
            else:
                rest.append(c)
        return money, rest

    rural_left, rural_rest = fill(rural_pool, rural_budget, "Funded from rural reserve: best value among village/ODR roads")
    main_left, main_rest = fill(main_pool, main_budget + rural_left, "Funded: high people-benefit per rupee")
    main_left, rural_rest = fill(rural_rest, main_left, "Funded with leftover budget")
    left = main_left
    for i, c in enumerate(sorted(main_rest + rural_rest, key=lambda c: -c["value"]), 1):
        c["reason"] = f"Deferred: budget exhausted (next in line #{i})"
        deferred.append(c)

    spent = sum(c["cost"] for c in funded)
    return {
        "budget": budget, "rural_share": rural_share, "spent": spent, "left": left,
        "summary": {
            "works_funded": len(funded),
            "daily_users_benefiting": sum(c["daily_users"] for c in funded + free),
            "future_cost_avoided": sum(c.get("avoided", 0) for c in funded),
            "free_fixes": len(free),
            "blocked_payments": sum(c["cost"] for c in blocked),
            "rural_works": sum(1 for c in funded if c["rural"]),
            "rural_spend": sum(c["cost"] for c in funded if c["rural"]),
        },
        "free": free, "blocked": blocked, "funded": funded, "deferred": deferred,
        "assumptions": {
            "recarpet_rate_per_km": RECARPET_PER_KM, "reconstruct_factor": RECONSTRUCT_FACTOR,
            "early_action_bonus": EARLY_ACTION_BONUS, "failure_probability": FAILURE_PROB, "bridge_rehab": BRIDGE_REHAB, "culvert_fix": CULVERT_FIX,
            "building_rate_sqm": BUILDING_RATE_SQM,
            "value_formula": "value = daily users × need × criticality × span × early-action bonus ÷ cost (₹ crore)",
        },
    }
