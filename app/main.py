"""Pravi — R&B Asset Lifecycle Tracker (FastAPI app)."""
import json
import re
import time
from contextlib import asynccontextmanager
import uuid
from collections import defaultdict, deque
from datetime import date, datetime, timedelta
from difflib import get_close_matches
from typing import Optional

from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select

from . import extraction
from .auth import COOKIE, EE, FIELD, STAFF, make_token, require_role, set_auth_cookie, verify_password
from .config import DISTRICT, LLM_MODEL, LLM_PROVIDER, JWT_SECRET_FROM_ENV, RESET_DB_ON_START, SAMPLE_DIR, FRONTEND_DIST, SEED_DEMO
from .db import engine, get_session, init_db
from .geo import haversine, snap
from .models import Asset, Complaint, Document, Event, Inspection, Photo, Setting, User, Work
from .photos import save_photo
from .planner import plan as budget_plan
from .rules import (DEFAULT_WEIGHTS, WORK_LABEL, add_months, compute_flags, contractor_scorecard, lakh,
                    liability_summary, liability_windows, load_ctx, money_at_risk, priority, works_on)
from .seed import seed, seed_if_empty

def _startup():
    init_db(reset=RESET_DB_ON_START)
    try:
        with Session(engine) as s:
            if seed_if_empty(s, demo=SEED_DEMO):
                print("[startup] seeded " + ("demo data" if SEED_DEMO else "login accounts only (SEED_DEMO=false)"))
    except Exception as e:  # e.g. two serverless instances seeding at the same moment
        print(f"[startup] seeding skipped: {type(e).__name__}")
    if not JWT_SECRET_FROM_ENV:
        print("[startup] WARNING: JWT_SECRET not set; set it in production")
    print(f"[startup] document reading: rules" + (f" + LLM ({LLM_PROVIDER}: {LLM_MODEL})" if LLM_PROVIDER != "none" else " only"))


@asynccontextmanager
async def lifespan(_app):
    _startup()
    yield


app = FastAPI(title="Pravi — R&B Asset Lifecycle Tracker", version="1.0", lifespan=lifespan,
              description="Lifecycle inventory, liability tracking and priority for Gujarat R&B assets (demo: Vadodara).")


# ------------------------------------------------------------------ helpers

ISSUE_TYPES = {
    "pothole": "Pothole", "crack": "Cracks / broken surface", "waterlogging": "Waterlogging",
    "signage": "Damaged sign / marking", "railing": "Broken railing / barrier",
    "leakage": "Leakage (building)", "other": "Other",
}
STATUS_ORDER = ["proposed", "sanctioned", "tendered", "awarded", "under_construction", "completed"]
BAND_COLOR = {"Urgent": "#b42318", "This week": "#d92d20", "This month": "#f79009", "Next season": "#eaaa08",
              "Monitor": "#12b76a"}


def jload(s, default=None):
    try:
        return json.loads(s) if s else (default if default is not None else {})
    except ValueError:
        return default if default is not None else {}


def d_iso(x):
    return x.isoformat() if x else None


def add_event(session, asset_id, etype, message, actor="system", work_id=None, complaint_id=None, on: Optional[date] = None):
    ev = Event(asset_id=asset_id, event_type=etype, message=message, actor=actor, work_id=work_id, complaint_id=complaint_id)
    if on and on < date.today():  # back-dated documents appear at their real date on the timeline
        ev.happened_at = datetime.combine(on, datetime.min.time()).replace(hour=10)
    session.add(ev)


def asset_brief(a: Asset) -> dict:
    return {"id": a.id, "code": a.code, "type": a.asset_type, "name": a.name, "category": a.category,
            "road_code": a.road_code, "start_km": a.start_km, "end_km": a.end_km, "chainage_km": a.chainage_km,
            "lat": a.lat, "lng": a.lng, "taluka": a.taluka}


def work_dict(w: Work) -> dict:
    return {"id": w.id, "asset_id": w.asset_id, "road_code": w.road_code, "start_km": w.start_km,
            "end_km": w.end_km, "work_type": w.work_type, "work_label": WORK_LABEL.get(w.work_type, w.work_type),
            "title": w.title, "status": w.status, "contractor": w.contractor, "estimated_cost": w.estimated_cost,
            "awarded_cost": w.awarded_cost, "tender_id": w.tender_id, "proposed_on": d_iso(w.proposed_on),
            "sanctioned_on": d_iso(w.sanctioned_on), "tendered_on": d_iso(w.tendered_on),
            "awarded_on": d_iso(w.awarded_on), "started_on": d_iso(w.started_on), "due_on": d_iso(w.due_on),
            "completed_on": d_iso(w.completed_on), "liability_months": w.liability_months,
            "liability_end": d_iso(w.liability_end), "liability_estimated": w.liability_estimated,
            "completion_period_days": w.completion_period_days, "reason": w.reason, "source": w.source}


def complaint_dict(c: Complaint, asset: Optional[Asset] = None) -> dict:
    return {"id": c.id, "ticket": c.ticket, "asset_id": c.asset_id,
            "asset_name": asset.name if asset else None, "asset_code": asset.code if asset else None,
            "road_code": asset.road_code if asset else None, "lat": c.lat, "lng": c.lng, "km": c.km,
            "issue_type": c.issue_type, "issue_label": ISSUE_TYPES.get(c.issue_type, c.issue_type),
            "description": c.description, "language": c.language, "report_count": c.report_count,
            "status": c.status, "liable_contractor": c.liable_contractor, "liable_until": d_iso(c.liable_until),
            "liable_work_id": c.liable_work_id, "assigned_kind": c.assigned_kind, "assigned_to": c.assigned_to,
            "condition": c.condition, "verify_notes": c.verify_notes, "fix_notes": c.fix_notes,
            "photo_url": f"/api/photos/{c.photo_id}" if c.photo_id else None,
            "fix_photo_url": f"/api/photos/{c.fix_photo_id}" if c.fix_photo_id else None,
            "reopened_count": c.reopened_count,
            "created_at": c.created_at.isoformat(), "verified_at": d_iso(c.verified_at),
            "assigned_at": d_iso(c.assigned_at), "fixed_at": d_iso(c.fixed_at), "closed_at": d_iso(c.closed_at),
            "age_days": (datetime.utcnow() - c.created_at).days}


# ------------------------------------------------------------------ pages

# The React app (frontend/) is built into frontend/dist and served at the end of this file.

@app.get("/samples/{name}", include_in_schema=False)
def sample_file(name: str):
    p = SAMPLE_DIR / name
    if "/" in name or ".." in name or not p.exists():
        raise HTTPException(404)
    return FileResponse(p)


@app.get("/api/samples")
def list_samples():
    return [{"name": p.name, "url": f"/samples/{p.name}"} for p in sorted(SAMPLE_DIR.glob("*.pdf"))]


@app.get("/api/health")
def health():
    return {"ok": True, "extraction": "rules" if LLM_PROVIDER == "none" else f"rules + {LLM_PROVIDER} ({LLM_MODEL})"}


# ------------------------------------------------------------------ auth

@app.post("/api/auth/login")
def login(request: Request, response: Response, body: dict = Body(...), session: Session = Depends(get_session)):
    u = session.exec(select(User).where(User.username == (body.get("username") or "").strip())).first()
    if not u or not verify_password(body.get("password") or "", u.password_hash):
        raise HTTPException(401, "Wrong username or password")
    set_auth_cookie(response, request, make_token(u))
    return {"username": u.username, "name": u.full_name, "role": u.role, "district": u.district}


@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@app.get("/api/auth/me")
def me(user=Depends(STAFF)):
    return {"username": user["username"], "name": user["name"], "role": user["role"], "district": user["district"]}


# ------------------------------------------------------------------ photos

@app.get("/api/photos/{pid}")
def photo(pid: int, session: Session = Depends(get_session)):
    p = session.get(Photo, pid)
    if not p:
        raise HTTPException(404)
    return Response(p.data, media_type=p.mime, headers={"Cache-Control": "max-age=86400"})


# ------------------------------------------------------------------ public (citizen)

_hits = defaultdict(deque)


def rate_limit(request: Request, limit=20, window=3600):
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "?")).split(",")[0]
    q = _hits[ip]
    now = time.time()
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "Too many reports from this device. Please try again later.")
    q.append(now)


@app.get("/api/public/issue-types")
def issue_types():
    return ISSUE_TYPES


@app.get("/api/public/map")
def public_map(session: Session = Depends(get_session)):
    out = []
    for a in session.exec(select(Asset).where(Asset.district == DISTRICT)).all():
        item = asset_brief(a)
        item["geometry"] = jload(a.geometry, []) if a.geometry else None
        out.append(item)
    return out


def snap_location(session: Session, lat: float, lng: float, issue: str):
    """Find which asset a citizen's report belongs to."""
    assets = session.exec(select(Asset).where(Asset.district == DISTRICT)).all()
    best_road = (float("inf"), None, None)
    for a in assets:
        if a.asset_type != "road_section" or not a.geometry:
            continue
        dist, frac = snap((lat, lng), jload(a.geometry, []))
        if dist < best_road[0]:
            best_road = (dist, a, round(a.start_km + frac * (a.end_km - a.start_km), 1))
    prefer = {"railing": "bridge", "waterlogging": "culvert", "leakage": "building"}.get(issue)
    best_point = (float("inf"), None)
    for a in assets:
        if a.asset_type == "road_section" or a.lat is None:
            continue
        dist = haversine((lat, lng), (a.lat, a.lng))
        limit = 400 if a.asset_type == prefer else 120
        if dist <= limit and dist < best_point[0]:
            best_point = (dist, a)
    if best_point[1] and (best_point[1].asset_type == prefer or best_point[0] < best_road[0]):
        a = best_point[1]
        return a, a.chainage_km, best_point[0]
    if best_road[1] and best_road[0] <= 2000:
        return best_road[1], best_road[2], best_road[0]
    return None, None, None


@app.post("/api/public/complaints")
async def create_complaint(request: Request, lat: float = Form(...), lng: float = Form(...),
                           issue_type: str = Form(...), description: str = Form(""), language: str = Form("en"),
                           contact: str = Form(""), photo: Optional[UploadFile] = File(None),
                           session: Session = Depends(get_session)):
    rate_limit(request)
    if issue_type not in ISSUE_TYPES:
        raise HTTPException(400, "Unknown issue type")
    asset, km, dist = snap_location(session, lat, lng, issue_type)
    if not asset:
        raise HTTPException(422, "This spot is not on a road or building maintained by R&B Vadodara. "
                                 "Please move the pin onto the road.")
    # merge duplicates: same asset, same issue, within 300 m, still open
    for c in session.exec(select(Complaint).where(Complaint.asset_id == asset.id,
                                                  Complaint.issue_type == issue_type)).all():
        if c.status in ("open", "verified", "assigned") and haversine((lat, lng), (c.lat, c.lng)) <= 300:
            c.report_count += 1
            c.updated_at = datetime.utcnow()
            session.add(c)
            add_event(session, asset.id, "complaint_merged",
                      f"Another citizen reported the same {issue_type} — now {c.report_count} reports on {c.ticket}",
                      actor="Citizen", complaint_id=c.id)
            session.commit()
            return {"ticket": c.ticket, "merged": True, "report_count": c.report_count,
                    "asset": asset.name, "km": c.km, "liable_contractor": c.liable_contractor}
    pid = await save_photo(session, photo)
    c = Complaint(ticket="tmp-" + uuid.uuid4().hex[:10], asset_id=asset.id, lat=lat, lng=lng, km=km,
                  issue_type=issue_type, description=description[:1000], language=language[:5],
                  photo_id=pid, reporter_contact=contact[:40] or None, district=DISTRICT)
    ctx = load_ctx(session, DISTRICT)
    a_ctx = ctx.assets[asset.id]
    wins = liability_windows(ctx, a_ctx, km, km) if asset.asset_type == "road_section" and km is not None \
        else liability_windows(ctx, a_ctx)
    if wins:
        c.liable_work_id, c.liable_contractor, c.liable_until = wins[0].id, wins[0].contractor, wins[0].liability_end
    session.add(c)
    session.flush()
    c.ticket = f"GJ-VAD-{10240 + c.id}"
    session.add(c)
    where = f"{asset.road_name or asset.road_code} km {km:g}" if asset.road_code and km is not None else asset.name
    add_event(session, asset.id, "complaint_reported", f"Citizen reported {issue_type} at {where} ({c.ticket})",
              actor="Citizen", complaint_id=c.id)
    if c.liable_contractor:
        add_event(session, asset.id, "liability_check",
                  f"Under liability: {c.liable_contractor} until {c.liable_until:%d %b %Y}", complaint_id=c.id)
    session.commit()
    return {"ticket": c.ticket, "merged": False, "report_count": 1, "asset": asset.name, "km": km,
            "liable_contractor": c.liable_contractor, "liable_until": d_iso(c.liable_until)}


@app.get("/api/public/complaints/{ticket}")
def track_complaint(ticket: str, session: Session = Depends(get_session)):
    c = session.exec(select(Complaint).where(Complaint.ticket == ticket.strip().upper())).first()
    if not c:
        raise HTTPException(404, "Ticket not found")
    a = session.get(Asset, c.asset_id)
    d = complaint_dict(c, a)
    d.pop("verify_notes", None)
    evs = session.exec(select(Event).where(Event.complaint_id == c.id).order_by(Event.happened_at)).all()
    d["events"] = [{"type": e.event_type, "message": e.message, "at": e.happened_at.isoformat()} for e in evs]
    return d


@app.post("/api/public/complaints/{ticket}/confirm")
def confirm_fix(ticket: str, fixed: bool = Form(...), session: Session = Depends(get_session)):
    c = session.exec(select(Complaint).where(Complaint.ticket == ticket.strip().upper())).first()
    if not c:
        raise HTTPException(404, "Ticket not found")
    if c.status != "fixed":
        raise HTTPException(400, "This complaint is not waiting for confirmation")
    now = datetime.utcnow()
    if fixed:
        c.status, c.closed_at = "closed", now
        add_event(session, c.asset_id, "complaint_closed", f"Citizen confirmed fix; {c.ticket} closed",
                  actor="Citizen", complaint_id=c.id)
    else:
        c.status, c.reopened_count, c.fixed_at = "assigned", c.reopened_count + 1, None
        c.assigned_at = now
        add_event(session, c.asset_id, "complaint_reopened",
                  f"Citizen says NOT fixed; {c.ticket} reopened and sent back to {c.assigned_to}",
                  actor="Citizen", complaint_id=c.id)
    c.updated_at = now
    session.add(c)
    session.commit()
    return {"status": c.status}


# ------------------------------------------------------------------ dashboard & assets

def asset_row(ctx, a, flags_by_asset):
    pr = priority(ctx, a)
    li = liability_summary(ctx, a)
    fl = flags_by_asset.get(a.id, [])
    row = asset_brief(a)
    row.update({"score": pr["score"], "band": pr["band"], "urgent": pr["urgent"], "action": pr["action"],
                "color": BAND_COLOR[pr["band"]], "under_liability": li["under_liability"],
                "liable_contractor": li.get("contractor"), "liable_until": li.get("until"),
                "flags": len(fl), "red_flags": sum(1 for f in fl if f["severity"] == "red"),
                "open_complaints": sum(1 for c in ctx.complaints.get(a.id, []) if c.status in ("open", "verified", "assigned")),
                "condition": pr["inputs"]["condition"]})
    return row


def _flags_by_asset(flags):
    out = defaultdict(list)
    for f in flags:
        out[f["asset_id"]].append(f)
    return out


@app.get("/api/dashboard")
def dashboard(user=Depends(STAFF), session: Session = Depends(get_session)):
    ctx = load_ctx(session, user["district"])
    flags = compute_flags(ctx)
    fba = _flags_by_asset(flags)
    rows = [asset_row(ctx, a, fba) for a in ctx.assets.values()]
    for r in rows:
        a = ctx.assets[r["id"]]
        r["geometry"] = jload(a.geometry, []) if a.geometry else None
    ranked = sorted(rows, key=lambda r: (not r["urgent"], -r["score"]))
    comps = [c for cs in ctx.complaints.values() for c in cs]
    by_type = defaultdict(int)
    for a in ctx.assets.values():
        by_type[a.asset_type] += 1
    road_km = sum((a.end_km - a.start_km) for a in ctx.assets.values() if a.asset_type == "road_section")
    liab_km = 0.0
    for a in ctx.assets.values():
        if a.asset_type == "road_section":
            for w in liability_windows(ctx, a):
                liab_km += max(0, min(w.end_km, a.end_km) - max(w.start_km, a.start_km))
    return {
        "district": user["district"],
        "kpis": {
            "assets": len(ctx.assets), "by_type": by_type, "road_km": road_km,
            "road_km_under_liability": round(liab_km, 1),
            "open_complaints": sum(1 for c in comps if c.status in ("open", "verified", "assigned")),
            "awaiting_confirmation": sum(1 for c in comps if c.status == "fixed"),
            "red_flags": sum(1 for f in flags if f["severity"] == "red"),
            "flags": len(flags),
            "money_at_risk": money_at_risk(flags),
            "urgent": sum(1 for r in rows if r["urgent"]),
            "contractor_liable_open": sum(1 for c in comps if c.liable_contractor and c.status in ("open", "verified", "assigned")),
            "new_complaints": sum(1 for c in comps if c.status == "open"),
            "to_assign": sum(1 for c in comps if c.status == "verified"),
            "paid_in_liability": sum(1 for f in flags if f["type"] == "paid_repair_in_liability"),
            "notices_ignored": sum(1 for f in flags if f["type"] == "contractor_non_compliance"),
            "docs_to_review": len(session.exec(select(Document).where(Document.district == user["district"],
                                                                     Document.status == "review")).all()),
            "delayed_works": sum(1 for f in flags if f["type"] == "delayed_work"),
        },
        "flags": flags,
        "top": ranked[:10],
        "assets": rows,
    }


@app.get("/api/assets")
def list_assets(type: Optional[str] = None, q: Optional[str] = None, user=Depends(STAFF),
                session: Session = Depends(get_session)):
    ctx = load_ctx(session, user["district"])
    fba = _flags_by_asset(compute_flags(ctx))
    rows = [asset_row(ctx, a, fba) for a in ctx.assets.values()
            if (not type or a.asset_type == type) and (not q or q.lower() in (a.name + a.code).lower())]
    return sorted(rows, key=lambda r: (not r["urgent"], -r["score"]))


@app.get("/api/assets/{aid}")
def asset_detail(aid: int, user=Depends(STAFF), session: Session = Depends(get_session)):
    ctx = load_ctx(session, user["district"])
    a = ctx.assets.get(aid)
    if not a:
        raise HTTPException(404)
    flags = [f for f in compute_flags(ctx) if f["asset_id"] == aid]
    works = sorted(works_on(ctx, a), key=lambda w: (w.completed_on or w.awarded_on or w.tendered_on
                                                     or w.proposed_on or date.min), reverse=True)
    evq = select(Event).where(Event.asset_id == aid)
    events = session.exec(evq.order_by(Event.happened_at.desc())).all()
    # include events of works that touch this stretch but are filed under another section
    other_ids = [w.id for w in works if w.asset_id != aid]
    if other_ids:
        events += session.exec(select(Event).where(Event.work_id.in_(other_ids))).all()
        events.sort(key=lambda e: e.happened_at, reverse=True)
    docs = session.exec(select(Document).where(Document.work_id.in_([w.id for w in works] or [-1]))).all()
    return {
        "asset": {**asset_brief(a), "attrs": jload(a.attrs), "year_built": a.year_built, "status": a.status,
                  "road_name": a.road_name, "division": a.division, "district": a.district,
                  "geometry": jload(a.geometry, []) if a.geometry else None},
        "priority": priority(ctx, a),
        "liability": liability_summary(ctx, a),
        "flags": flags,
        "works": [work_dict(w) for w in works],
        "inspections": [{"id": i.id, "kind": i.kind, "date": d_iso(i.inspected_on), "condition": i.condition,
                         "notes": i.notes, "inspector": i.inspector,
                         "photo_url": f"/api/photos/{i.photo_id}" if i.photo_id else None}
                        for i in ctx.inspections.get(aid, [])],
        "complaints": [complaint_dict(c, a) for c in sorted(ctx.complaints.get(aid, []),
                                                            key=lambda c: c.created_at, reverse=True)],
        "documents": [{"id": d.id, "doc_type": d.doc_type, "filename": d.filename, "work_id": d.work_id,
                       "method": d.method, "status": d.status, "has_file": d.file_bytes is not None,
                       "created_at": d.created_at.isoformat()} for d in docs],
        "timeline": [{"type": e.event_type, "message": e.message, "actor": e.actor, "at": e.happened_at.isoformat(),
                      "work_id": e.work_id, "complaint_id": e.complaint_id} for e in events],
    }


@app.post("/api/assets/{aid}/inspections")
async def add_inspection(aid: int, kind: str = Form("inspection"), condition: Optional[int] = Form(None),
                         notes: str = Form(""), inspected_on: Optional[str] = Form(None),
                         photo: Optional[UploadFile] = File(None), user=Depends(FIELD),
                         session: Session = Depends(get_session)):
    a = session.get(Asset, aid)
    if not a or a.district != user["district"]:
        raise HTTPException(404)
    if kind not in ("inspection", "cleaning", "structural_audit"):
        raise HTTPException(400, "Unknown inspection kind")
    if condition is not None and not 1 <= condition <= 5:
        raise HTTPException(400, "Condition must be 1–5")
    pid = await save_photo(session, photo)
    day = extraction.to_date(inspected_on) or date.today()
    i = Inspection(asset_id=aid, kind=kind, inspected_on=day, condition=condition, notes=notes,
                   inspector=user["name"], photo_id=pid)
    session.add(i)
    label = {"inspection": "Inspection", "cleaning": "Cleaning", "structural_audit": "Structural audit"}[kind]
    add_event(session, aid, kind, f"{label}: " + (f"condition {condition}/5. " if condition else "") + notes,
              actor=user["name"])
    session.commit()
    return {"ok": True, "id": i.id}


@app.get("/api/flags")
def flags(user=Depends(STAFF), session: Session = Depends(get_session)):
    return compute_flags(load_ctx(session, user["district"]))


# ------------------------------------------------------------------ complaints (staff)

@app.get("/api/complaints")
def list_complaints(status: Optional[str] = None, user=Depends(STAFF), session: Session = Depends(get_session)):
    q = select(Complaint).where(Complaint.district == user["district"])
    if status:
        q = q.where(Complaint.status.in_(status.split(",")))
    cs = session.exec(q.order_by(Complaint.created_at.desc())).all()
    assets = {a.id: a for a in session.exec(select(Asset)).all()}
    return [complaint_dict(c, assets.get(c.asset_id)) for c in cs]


def _get_complaint(session, cid, user) -> Complaint:
    c = session.get(Complaint, cid)
    if not c or c.district != user["district"]:
        raise HTTPException(404)
    return c


@app.post("/api/complaints/{cid}/verify")
def verify_complaint(cid: int, body: dict = Body(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    c = _get_complaint(session, cid, user)
    if c.status != "open":
        raise HTTPException(400, f"Complaint is already {c.status}")
    now = datetime.utcnow()
    if not body.get("approve", True):
        c.status, c.closed_at = "rejected", now
        c.verify_notes = body.get("notes") or "Not an R&B issue / duplicate"
        add_event(session, c.asset_id, "complaint_rejected", f"{c.ticket} rejected: {c.verify_notes}",
                  actor=user["name"], complaint_id=c.id)
    else:
        c.status, c.verified_at = "verified", now
        c.condition = body.get("condition")
        c.verify_notes = body.get("notes")
        add_event(session, c.asset_id, "complaint_verified",
                  f"{c.ticket} verified on site" + (f", condition {c.condition}/5" if c.condition else ""),
                  actor=user["name"], complaint_id=c.id)
        if c.condition:
            session.add(Inspection(asset_id=c.asset_id, kind="inspection", inspected_on=date.today(),
                                   condition=int(c.condition), notes=f"While verifying {c.ticket}: {c.verify_notes or ''}",
                                   inspector=user["name"]))
    c.updated_at = now
    session.add(c)
    session.commit()
    return complaint_dict(c)


@app.post("/api/complaints/{cid}/assign")
def assign_complaint(cid: int, body: dict = Body(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    c = _get_complaint(session, cid, user)
    if c.status not in ("verified", "assigned"):
        raise HTTPException(400, "Verify the complaint first")
    kind = body.get("kind", "contractor" if c.liable_contractor else "department")
    if kind == "contractor" and not c.liable_contractor:
        raise HTTPException(400, "No contractor is liable for this spot")
    c.assigned_kind = kind
    c.assigned_to = c.liable_contractor if kind == "contractor" else (body.get("to") or "Department maintenance gang")
    c.status, c.assigned_at, c.updated_at = "assigned", datetime.utcnow(), datetime.utcnow()
    msg = (f"Defect notice issued to {c.assigned_to} (liable until {c.liable_until:%d %b %Y}) — ₹0 to department"
           if kind == "contractor" else f"{c.ticket} assigned to {c.assigned_to}")
    add_event(session, c.asset_id, "complaint_assigned", msg, actor=user["name"], complaint_id=c.id)
    session.add(c)
    session.commit()
    return complaint_dict(c)


@app.post("/api/complaints/{cid}/fix")
async def fix_complaint(cid: int, notes: str = Form(""), photo: Optional[UploadFile] = File(None),
                        user=Depends(FIELD), session: Session = Depends(get_session)):
    c = _get_complaint(session, cid, user)
    if c.status != "assigned":
        raise HTTPException(400, "Only assigned complaints can be marked fixed")
    c.fix_photo_id = await save_photo(session, photo)
    c.fix_notes = notes
    c.status, c.fixed_at, c.updated_at = "fixed", datetime.utcnow(), datetime.utcnow()
    add_event(session, c.asset_id, "complaint_fixed",
              f"{c.ticket} marked fixed by {c.assigned_to}" + (" with photo" if c.fix_photo_id else "")
              + " — waiting for citizen confirmation", actor=user["name"], complaint_id=c.id)
    session.add(c)
    session.commit()
    return complaint_dict(c)


@app.get("/api/complaints/{cid}/notice", response_class=HTMLResponse)
def defect_notice(cid: int, user=Depends(STAFF), session: Session = Depends(get_session)):
    c = _get_complaint(session, cid, user)
    if not c.liable_contractor:
        raise HTTPException(400, "No contractor liability for this complaint")
    a = session.get(Asset, c.asset_id)
    w = session.get(Work, c.liable_work_id) if c.liable_work_id else None
    today = date.today()
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Defect notice {c.ticket}</title>
<style>body{{font:15px/1.6 Georgia,serif;max-width:720px;margin:40px auto;padding:0 20px;color:#111}}
h2{{text-align:center;margin-bottom:0}}.sub{{text-align:center;color:#555;margin-top:4px}}
table{{border-collapse:collapse;width:100%;margin:16px 0}}td{{border:1px solid #bbb;padding:6px 10px;vertical-align:top}}
td:first-child{{width:38%;color:#444}}.draft{{border:2px dashed #b42318;color:#b42318;padding:6px 10px;text-align:center;font-family:sans-serif;font-size:13px}}
@media print{{.noprint{{display:none}}}}</style></head><body>
<div class="draft">DRAFT generated by Pravi (demo) — to be verified and signed by the Executive Engineer</div>
<h2>Notice to rectify defects within the Defect Liability Period</h2>
<p class="sub">Roads &amp; Buildings Division, {a.district} &nbsp;·&nbsp; Date: {today:%d %b %Y}</p>
<p>To,<br><b>{c.liable_contractor}</b></p>
<p>Subject: Rectification of defects under the Defect Liability Period — {w.tender_id if w and w.tender_id else ''}</p>
<table>
<tr><td>Name of work</td><td>{w.title if w else '-'}</td></tr>
<tr><td>Location</td><td>{a.name}{f', at km {c.km:g}' if c.km is not None else ''}</td></tr>
<tr><td>Work completed on</td><td>{w.completed_on.strftime('%d %b %Y') if w and w.completed_on else '-'}</td></tr>
<tr><td>Defect Liability Period ends</td><td>{c.liable_until:%d %b %Y}</td></tr>
<tr><td>Defect reported</td><td>{ISSUE_TYPES.get(c.issue_type, c.issue_type)} — {c.report_count} citizen report(s), ticket {c.ticket}, first reported {c.created_at:%d %b %Y}</td></tr>
<tr><td>Verified on site</td><td>{c.verified_at.strftime('%d %b %Y') if c.verified_at else 'Pending'}{f' — condition {c.condition}/5' if c.condition else ''}</td></tr>
</table>
<p>The above defect has appeared within the Defects Liability Period of the contract. As per <b>Clause 17-A</b> of the
contract (Form B-1), you are required to make good and remedy the defect at your own expense within <b>15 days</b> of
receipt of this notice. If the defect is not rectified, the Department may get the work done at your risk and cost and
recover the amount from your security deposit / dues.</p>
<p style="margin-top:48px">Executive Engineer<br>Roads &amp; Buildings Division, {a.district}</p>
<p class="noprint"><button onclick="print()">Print / save as PDF</button></p></body></html>"""


# ------------------------------------------------------------------ works

@app.get("/api/works")
def list_works(status: Optional[str] = None, user=Depends(STAFF), session: Session = Depends(get_session)):
    q = select(Work).where(Work.district == user["district"])
    if status:
        q = q.where(Work.status.in_(status.split(",")))
    ws = session.exec(q).all()
    assets = {a.id: a for a in session.exec(select(Asset)).all()}
    ctx = load_ctx(session, user["district"])
    flagged = defaultdict(list)
    for f in compute_flags(ctx):
        if f["work_id"]:
            flagged[f["work_id"]].append({"severity": f["severity"], "title": f["title"]})
    out = []
    for w in ws:
        d = work_dict(w)
        d["asset_name"] = assets[w.asset_id].name if w.asset_id in assets else None
        d["asset_code"] = assets[w.asset_id].code if w.asset_id in assets else None
        d["flags"] = flagged.get(w.id, [])
        out.append(d)
    order = {s: i for i, s in enumerate(STATUS_ORDER + ["cancelled"])}
    return sorted(out, key=lambda d: (order.get(d["status"], 9), d["proposed_on"] or ""))


def _liability_warning(session, asset: Asset, k0, k1, on: date, exclude_id=None):
    ctx = load_ctx(session, asset.district)
    a = ctx.assets[asset.id]
    wins = liability_windows(ctx, a, k0, k1, on=on, exclude_work_id=exclude_id) if a.asset_type == "road_section" \
        else liability_windows(ctx, a, on=on, exclude_work_id=exclude_id)
    if not wins:
        return None
    w = wins[0]
    return {"contractor": w.contractor, "until": d_iso(w.liability_end), "work_id": w.id, "work_title": w.title,
            "message": f"This stretch is under defect liability with {w.contractor} until {w.liability_end:%d %b %Y}. "
                       f"Defect repairs here should cost the department ₹0."}


@app.post("/api/works")
def propose_work(body: dict = Body(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    a = session.get(Asset, int(body.get("asset_id") or 0))
    if not a or a.district != user["district"]:
        raise HTTPException(400, "Pick an asset")
    wt = body.get("work_type")
    if wt not in WORK_LABEL:
        raise HTTPException(400, "Pick a work type")
    k0 = body.get("start_km")
    k1 = body.get("end_km")
    if a.asset_type == "road_section":
        k0 = float(k0) if k0 not in (None, "") else a.start_km
        k1 = float(k1) if k1 not in (None, "") else a.end_km
        if k0 >= k1:
            raise HTTPException(400, "Start km must be less than end km")
    else:
        k0 = k1 = None
    w = Work(asset_id=a.id, road_code=a.road_code if a.asset_type == "road_section" else None, start_km=k0,
             end_km=k1, work_type=wt,
             title=body.get("title") or f"{WORK_LABEL[wt]} of {a.name}",
             status="proposed", estimated_cost=float(body.get("estimated_cost") or 0) or None,
             proposed_on=date.today(), reason=body.get("reason"), source="manual", created_by=user["name"],
             liability_months=int(body["liability_months"]) if body.get("liability_months") else None,
             district=user["district"])
    session.add(w)
    session.flush()
    add_event(session, a.id, "work_proposed", f"Proposed: {w.title}" + (f" — {w.reason}" if w.reason else ""),
              actor=user["name"], work_id=w.id)
    warn = _liability_warning(session, a, k0, k1, date.today(), exclude_id=w.id) if wt in \
        {"repair", "recarpet", "rehab", "waterproofing", "structural_repair", "widening"} else None
    if warn:
        add_event(session, a.id, "liability_warning", "Warning at proposal: " + warn["message"], work_id=w.id)
    session.commit()
    return {"work": work_dict(w), "liability_warning": warn}


@app.post("/api/works/{wid}/advance")
def advance_work(wid: int, body: dict = Body(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    w = session.get(Work, wid)
    if not w or w.district != user["district"]:
        raise HTTPException(404)
    to = body.get("to")
    today = extraction.to_date(body.get("date")) or date.today()
    if to == "cancelled":
        if user["role"] != "ee":
            raise HTTPException(403, "Only the Executive Engineer can cancel works")
        if w.status == "completed":
            raise HTTPException(400, "Completed works cannot be cancelled")
        w.status = "cancelled"
        add_event(session, w.asset_id, "work_cancelled", f"Cancelled: {w.title}" +
                  (f" — {body.get('reason')}" if body.get("reason") else ""), actor=user["name"], work_id=w.id)
        session.add(w)
        session.commit()
        return work_dict(w)
    if to not in STATUS_ORDER or w.status not in STATUS_ORDER:
        raise HTTPException(400, "Invalid status change")
    if STATUS_ORDER.index(to) != STATUS_ORDER.index(w.status) + 1:
        raise HTTPException(400, f"Next step after '{w.status}' is '{STATUS_ORDER[STATUS_ORDER.index(w.status) + 1]}'")
    if to == "sanctioned" and user["role"] != "ee":
        raise HTTPException(403, "Only the Executive Engineer can sanction works")
    msg = ""
    if to == "sanctioned":
        w.sanctioned_on = today
        if body.get("estimated_cost"):
            w.estimated_cost = float(body["estimated_cost"])
        msg = f"Sanctioned by {user['name']} (est. {lakh(w.estimated_cost)})"
    elif to == "tendered":
        w.tendered_on = today
        w.tender_id = body.get("tender_id") or w.tender_id or f"RNB/VAD/{today.year}/{wid:04d}"
        if body.get("liability_months"):
            w.liability_months = int(body["liability_months"])
        msg = f"Tender {w.tender_id} published"
    elif to == "awarded":
        if not body.get("contractor"):
            raise HTTPException(400, "Contractor name is required")
        w.awarded_on, w.contractor = today, body["contractor"]
        w.awarded_cost = float(body.get("awarded_cost") or w.estimated_cost or 0) or None
        if body.get("completion_period_days"):
            w.completion_period_days = int(body["completion_period_days"])
            w.due_on = today + timedelta(days=w.completion_period_days)
        msg = f"Awarded to {w.contractor} for {lakh(w.awarded_cost)}"
    elif to == "under_construction":
        w.started_on = today
        msg = "Work started on site"
        a = session.get(Asset, w.asset_id)
        if a and w.work_type == "new_construction":
            a.status = "under_construction"
            session.add(a)
    elif to == "completed":
        w.completed_on = today
        if body.get("liability_months"):
            w.liability_months = int(body["liability_months"])
        if w.liability_months:
            w.liability_end = add_months(today, w.liability_months)
        a = session.get(Asset, w.asset_id)
        if a:
            a.status = "in_service"
            session.add(a)
        msg = f"Completed by {w.contractor or 'contractor'}" + (
            f". Defect liability {w.liability_months} months — clock starts today, ends {w.liability_end:%d %b %Y}"
            if w.liability_end else "")
    w.status = to
    add_event(session, w.asset_id, "work_" + to, msg, actor=user["name"], work_id=w.id)
    session.add(w)
    session.commit()
    a = session.get(Asset, w.asset_id)
    warn = None
    if to in ("sanctioned", "tendered") and w.work_type in {"repair", "recarpet", "rehab", "waterproofing", "structural_repair"}:
        warn = _liability_warning(session, a, w.start_km, w.end_km, today, exclude_id=w.id)
    return {**work_dict(w), "liability_warning": warn}


# ------------------------------------------------------------------ documents

def _name_tokens(name: str) -> set:
    t = re.sub(r"[^a-z0-9 ]", " ", (name or "").lower().replace("–", " ").replace("-", " "))
    stop = {"road", "rd", "to", "the", "of", "and", "approach", "km", "sh", "mdr", "odr", "vr", "village"}
    return {w for w in t.split() if w not in stop and not w.isdigit() and len(w) > 1}


def match_asset(session: Session, f: dict, district: str) -> Optional[Asset]:
    """Find the asset a document is about: asset code, road code + km, or road name (+ taluka) + km."""
    assets = session.exec(select(Asset).where(Asset.district == district)).all()
    if f.get("asset_code"):
        for a in assets:
            if a.code == f["asset_code"]:
                return a
    secs = []
    if f.get("road_code"):
        secs = [a for a in assets if a.asset_type == "road_section" and a.road_code == f["road_code"]]
    if not secs:
        want = _name_tokens(f.get("road_name") or "") or _name_tokens(f.get("title") or "")
        best, best_score = None, 0.0
        for code in {a.road_code for a in assets if a.asset_type == "road_section"}:
            road = next(a for a in assets if a.road_code == code)
            have = _name_tokens(road.road_name)
            if not have or not want:
                continue
            score = len(want & have) / len(have)          # share of the road's name words found
            if score < 0.6 or len(want - have) > len(have):  # most words must match; taluka only breaks ties
                continue
            if f.get("taluka") and road.taluka and f["taluka"].lower() == road.taluka.lower():
                score += 0.2
            if score > best_score:
                best, best_score = code, score
        if best and best_score >= 0.6:
            secs = [a for a in assets if a.asset_type == "road_section" and a.road_code == best]
    if secs:
        secs.sort(key=lambda a: a.start_km)
        k = f.get("start_km")
        if k is not None:
            for a in secs:
                if a.start_km <= k < a.end_km:
                    return a
            return secs[-1] if k >= secs[-1].end_km else secs[0]
        return secs[0]
    # buildings / bridges by name
    name = f.get("title") or ""
    others = [a for a in assets if a.asset_type != "road_section"]
    want = _name_tokens(name)
    scored = sorted(((len(want & _name_tokens(a.name)) / max(1, len(_name_tokens(a.name))), a) for a in others),
                    key=lambda x: -x[0])
    if scored and scored[0][0] >= 0.6:
        return scored[0][1]
    return None


def _guess_asset(f: dict) -> dict:
    """Decide what kind of asset a document describes when it is not in the inventory yet."""
    text = f"{f.get('title') or ''} {f.get('road_name') or ''}".lower()
    if "bridge" in text:
        return {"asset_type": "bridge", "category": "bridge"}
    if "culvert" in text:
        return {"asset_type": "culvert", "category": "culvert"}
    for kw, cat in [("hospital", "hospital"), ("school", "school"), ("college", "school"), ("hostel", "school"),
                    ("quarter", "quarters"), ("colony", "quarters"), ("bungalow", "quarters"), ("tower", "quarters"),
                    ("office", "office"), ("building", "office"), ("sadan", "office"), ("court", "office")]:
        if kw in text:
            return {"asset_type": "building", "category": cat}
    cat = "VR" if re.search(r"mmgsy|pmgsy|village|approach road|gram", text) else "ODR"
    if re.search(r"state highway|\bsh\b", text):
        cat = "SH"
    return {"asset_type": "road_section", "category": cat}


def _nominatim(q: str) -> Optional[tuple]:
    import httpx
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/search", timeout=8,
                      params={"q": q, "format": "json", "limit": 1, "countrycodes": "in"},
                      headers={"user-agent": "Pravi-RnB-asset-tracker/1.0 (hackathon prototype)"})
        hits = r.json()
        if hits:
            return float(hits[0]["lat"]), float(hits[0]["lon"])
    except Exception:
        pass
    return None


# Approximate centres of towns in the demo district, used before online geocoding so demos work offline.
GAZETTEER = {
    "vadodara": (22.3072, 73.1812), "padra": (22.2385, 73.0850), "dabhoi": (22.1837, 73.4290), "savli": (22.5667, 73.2200),
    "waghodia": (22.3050, 73.4000), "karjan": (22.0530, 73.1235), "sinor": (21.9140, 73.3390), "jarod": (22.4330, 73.3350),
    "desar": (22.6710, 73.2890), "chandod": (21.9920, 73.4470), "por": (22.1330, 73.1830), "jambusar": (22.0540, 72.8090),
}


def _place(name: str, ctx: str) -> Optional[tuple]:
    return GAZETTEER.get(name.strip().lower()) or _nominatim(f"{name.strip()}, {ctx}")


def _geocode(f: dict) -> Optional[tuple]:
    """Best-effort map position for a new asset: the taluka / place named in the document (OpenStreetMap Nominatim)."""
    if f.get("taluka") and f["taluka"].lower() in GAZETTEER:
        return GAZETTEER[f["taluka"].lower()]
    places = [p for p in [f.get("taluka"), f.get("district")] if p]
    return _nominatim(", ".join(places) + ", Gujarat, India") if places else None


def _road_line(f: dict) -> Optional[list]:
    """For 'A to B Road' / 'A-B Road', draw a straight line between the two places (approximate until GIS data)."""
    name = (f.get("road_name") or "").replace("–", "-")
    m = re.match(r"\s*([A-Za-z .]+?)\s*(?:\bto\b|-)\s*([A-Za-z .]+?)\s*(?:Approach\s+)?Road", name, re.I)
    if not m:
        return None
    ctx = ", ".join(p for p in [f.get("district") or f.get("taluka"), "Gujarat, India"] if p)
    a, b = _place(m.group(1), ctx), _place(m.group(2), ctx)
    if a and b and haversine(a, b) < 150_000:
        return [[round(a[0], 6), round(a[1], 6)], [round(b[0], 6), round(b[1], 6)]]
    return None


def _new_asset_from_doc(session: Session, f: dict, user: dict) -> Asset:
    kind = _guess_asset(f)
    prefix = {"road_section": "RS", "bridge": "BR", "culvert": "CU", "building": "BL"}[kind["asset_type"]]
    n = len(session.exec(select(Asset).where(Asset.asset_type == kind["asset_type"])).all()) + 1
    code = f"{user['district'][:3].upper()}-{prefix}-{n:03d}"
    while session.exec(select(Asset).where(Asset.code == code)).first():
        n += 1
        code = f"{user['district'][:3].upper()}-{prefix}-{n:03d}"
    is_road = kind["asset_type"] == "road_section"
    base_name = f.get("road_name") or (f.get("title") or "New asset")[:90]
    km = f" km {f['start_km']:g}–{f['end_km']:g}" if is_road and f.get("start_km") is not None and f.get("end_km") is not None else ""
    slug = re.sub(r"[^A-Z]", "", "".join(w[0] for w in re.findall(r"[A-Za-z]+", base_name.replace("Road", "")))[:4].upper()) or "X"
    line = _road_line(f) if is_road else None
    pos = ((line[0][0] + line[1][0]) / 2, (line[0][1] + line[1][1]) / 2) if line else _geocode(f)
    a = Asset(code=code, asset_type=kind["asset_type"], category=kind["category"], name=f"{base_name}{km}",
              road_code=f"{kind['category']}-{slug}{n}" if is_road else None, road_name=base_name if is_road else None,
              start_km=f.get("start_km") if is_road else None, end_km=f.get("end_km") if is_road else None,
              lat=pos[0] if pos else None, lng=pos[1] if pos else None, geometry=json.dumps(line) if line else None,
              attrs=json.dumps({k: v for k, v in {"source": "Created from document", "place_in_document":
                                ", ".join(p for p in [f.get("taluka") and f"Ta. {f['taluka']}", f.get("district") and f"Dist. {f['district']}"] if p) or None,
                                "scheme": f.get("scheme"), "location": ("approximate straight line between the two places" if line else
                                              "approximate (taluka centre)" if pos else "not mapped yet")}.items() if v}),
              district=user["district"], taluka=f.get("taluka"), status="proposed")
    session.add(a)
    session.flush()
    first = min([d for d in (extraction.to_date(f.get(k)) for k in ("sanction_date", "tender_date", "award_date", "completion_date")) if d] or [date.today()])
    add_event(session, a.id, "registered", f"Registered in inventory from a contract document: {a.name}", actor=user["name"],
              on=first - timedelta(days=1))
    return a


def _pending_work(session, asset: Optional[Asset]) -> Optional[Work]:
    """An approved (or proposed) work on this asset that has no tender yet — a tender document continues it."""
    if not asset:
        return None
    ws = session.exec(select(Work).where(Work.asset_id == asset.id, Work.status.in_(["proposed", "sanctioned"]))).all()
    ws = [w for w in ws if not w.tender_id]
    return sorted(ws, key=lambda w: w.id)[-1] if ws else None


def _preview(session, doc_fields: dict, asset: Optional[Asset], district: str) -> dict:
    """Explain what confirming this document will do, and warn about liability."""
    f = doc_fields
    existing = session.exec(select(Work).where(Work.tender_id == f.get("tender_id"))).first() if f.get("tender_id") else None
    if existing and not asset:
        asset = session.get(Asset, existing.asset_id)
    dt = f.get("doc_type")
    pending = _pending_work(session, asset) if (dt == "tender" and not existing) else None
    if dt == "sanction":
        effect = "Create a new work at stage 'Approved' (administrative approval / technical sanction)"
    elif dt == "tender" and pending:
        effect = f"Move the approved work #{pending.id} ('{pending.title[:60]}') to 'Tender out'"
        existing = pending
    elif dt == "tender":
        effect = f"Update work #{existing.id} with tender details" if existing else \
            "Create a new work at stage 'Tender out' on this asset"
    elif dt == "award":
        effect = f"Mark work #{existing.id} as Awarded to {f.get('contractor')}" if existing else \
            "No matching tender found — a new work will be created at stage 'Awarded'"
    elif dt == "completion":
        effect = (f"Mark work #{existing.id} as Completed and start the liability clock" if existing else
                  "No matching work found — a completed work will be created")
    else:
        effect = "Store document only"
    warn = None
    if asset and dt in ("tender", "award") and (f.get("work_type") or (existing and existing.work_type)) in \
            {"repair", "recarpet", "rehab", "waterproofing", "structural_repair"}:
        on = extraction.to_date(f.get("tender_date") or f.get("award_date")) or date.today()
        k0 = f.get("start_km") if f.get("start_km") is not None else (existing.start_km if existing else None)
        k1 = f.get("end_km") if f.get("end_km") is not None else (existing.end_km if existing else None)
        warn = _liability_warning(session, asset, k0 if asset.asset_type == "road_section" else None,
                                  k1 if asset.asset_type == "road_section" else None, on,
                                  exclude_id=existing.id if existing else None)
    return {"effect": effect, "existing_work_id": existing.id if existing else None, "liability_warning": warn}


def doc_dict(session, d: Document) -> dict:
    fields = jload(d.extracted)
    asset = session.get(Asset, d.asset_id) if d.asset_id else None
    return {"id": d.id, "doc_type": d.doc_type, "filename": d.filename, "method": d.method,
            "confidence": d.confidence, "status": d.status, "fields": fields, "work_id": d.work_id,
            "asset": asset_brief(asset) if asset else None, "uploaded_by": d.uploaded_by,
            "created_at": d.created_at.isoformat(), "text_preview": (d.text or "")[:1500],
            "preview": _preview(session, fields, asset, d.district) if d.status == "review" else None}


def _ingest_pdf(session: Session, user: dict, filename: str, data: bytes) -> dict:
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 15 MB)")
    if not data.startswith(b"%PDF"):
        raise HTTPException(400, "This is not a PDF file")
    try:
        text = extraction.pdf_text(data)
    except Exception:
        raise HTTPException(400, "Could not read this PDF")
    if len(text.strip()) < 40:
        raise HTTPException(422, "No text layer found — this looks like a scanned PDF. OCR is on the roadmap.")
    fields, method, conf = extraction.extract(text)
    asset = match_asset(session, fields, user["district"])
    d = Document(doc_type=fields.get("doc_type") or "other", filename=filename[:200], file_bytes=data, text=text,
                 extracted=json.dumps(fields), method=method, confidence=conf, status="review",
                 uploaded_by=user["name"], asset_id=asset.id if asset else None, district=user["district"])
    session.add(d)
    session.commit()
    return doc_dict(session, d)


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    data = await file.read()
    return _ingest_pdf(session, user, file.filename or "document.pdf", data)


def _safe_public_url(url: str) -> str:
    import ipaddress
    import socket
    from urllib.parse import urlparse
    u = urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        raise HTTPException(400, "Enter a full http(s) link to a PDF")
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == "https" else 80))
    except socket.gaierror:
        raise HTTPException(400, "Could not find that website")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise HTTPException(400, "That address is not allowed")
    return url.strip()


@app.post("/api/documents/from-url")
def import_document_url(body: dict = Body(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    """Download a public tender / work-order PDF (e.g. from nprocure or the R&B website) and read it."""
    import httpx
    url = _safe_public_url(body.get("url") or "")
    try:
        for _ in range(4):  # follow up to 3 redirects, re-checking each hop
            r = httpx.get(url, timeout=25, follow_redirects=False,
                          headers={"user-agent": "Mozilla/5.0 (Pravi asset tracker; tender import)"})
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = _safe_public_url(str(httpx.URL(url).join(r.headers["location"])))
                continue
            break
        r.raise_for_status()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"Could not download the PDF ({type(e).__name__}). "
                                 "Some government portals block automated downloads — download it and upload the file instead.")
    name = url.rstrip("/").split("/")[-1].split("?")[0] or "imported.pdf"
    return _ingest_pdf(session, user, name if name.lower().endswith(".pdf") else name + ".pdf", r.content)


@app.get("/api/documents")
def list_documents(user=Depends(STAFF), session: Session = Depends(get_session)):
    ds = session.exec(select(Document).where(Document.district == user["district"])
                      .order_by(Document.created_at.desc())).all()
    return [{"id": d.id, "doc_type": d.doc_type, "filename": d.filename, "method": d.method,
             "confidence": d.confidence, "status": d.status, "work_id": d.work_id, "asset_id": d.asset_id,
             "uploaded_by": d.uploaded_by, "created_at": d.created_at.isoformat(),
             "has_file": d.file_bytes is not None} for d in ds]


@app.get("/api/documents/{did}")
def get_document(did: int, user=Depends(STAFF), session: Session = Depends(get_session)):
    d = session.get(Document, did)
    if not d or d.district != user["district"]:
        raise HTTPException(404)
    return doc_dict(session, d)


@app.get("/api/documents/{did}/file")
def document_file(did: int, user=Depends(STAFF), session: Session = Depends(get_session)):
    d = session.get(Document, did)
    if not d or not d.file_bytes or d.district != user["district"]:
        raise HTTPException(404)
    return Response(d.file_bytes, media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="{d.filename}"'})


@app.post("/api/documents/{did}/preview")
def preview_document(did: int, body: dict = Body(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    d = session.get(Document, did)
    if not d or d.district != user["district"]:
        raise HTTPException(404)
    f = extraction.coerce(body.get("fields") or {})
    if str(body.get("asset_id") or "") == "new":
        kind = _guess_asset(f)
        pv = _preview(session, f, None, d.district)
        pv["effect"] = (f"Create a new {kind['asset_type'].replace('_', ' ')} '{f.get('road_name') or (f.get('title') or '')[:60]}' "
                        f"in the inventory, then: " + pv["effect"][0].lower() + pv["effect"][1:])
        return {"asset": None, "preview": pv}
    asset = session.get(Asset, int(body["asset_id"])) if body.get("asset_id") else match_asset(session, f, user["district"])
    return {"asset": asset_brief(asset) if asset else None, "preview": _preview(session, f, asset, d.district)}


@app.post("/api/documents/{did}/confirm")
def confirm_document(did: int, body: dict = Body(...), user=Depends(FIELD), session: Session = Depends(get_session)):
    d = session.get(Document, did)
    if not d or d.district != user["district"]:
        raise HTTPException(404)
    if d.status != "review":
        raise HTTPException(400, "Document already processed")
    f = extraction.coerce(body.get("fields") or jload(d.extracted))
    dt = f.get("doc_type")
    if dt not in ("sanction", "tender", "award", "completion"):
        raise HTTPException(400, "Set the document type (approval / tender / work order / completion)")
    existing = session.exec(select(Work).where(Work.tender_id == f.get("tender_id"))).first() if f.get("tender_id") else None
    choice = str(body.get("asset_id") or "")
    if choice == "new":
        asset = _new_asset_from_doc(session, f, user)
    elif choice:
        asset = session.get(Asset, int(choice))
    elif existing:
        asset = session.get(Asset, existing.asset_id)     # later documents of the same tender follow the same asset
    else:
        asset = match_asset(session, f, user["district"])
    if not asset:
        raise HTTPException(400, "No matching asset — pick one, or choose '+ Create new asset from this document'")
    is_road = asset.asset_type == "road_section"
    w = session.exec(select(Work).where(Work.tender_id == f.get("tender_id"))).first() if f.get("tender_id") else None
    if w is None and dt == "tender":
        w = _pending_work(session, asset)          # the tender continues an approved work
        if w is not None:
            w.tender_id = f.get("tender_id")
    new = w is None
    if new:
        w = Work(asset_id=asset.id, road_code=asset.road_code if is_road else None,
                 start_km=(f.get("start_km") if f.get("start_km") is not None else asset.start_km) if is_road else None,
                 end_km=(f.get("end_km") if f.get("end_km") is not None else asset.end_km) if is_road else None,
                 work_type=f.get("work_type") or "repair", title=f.get("title") or f"Work on {asset.name}",
                 tender_id=f.get("tender_id"), source="document", created_by=user["name"], district=user["district"])
    for k_src, k_dst in [("title", "title"), ("work_type", "work_type"), ("estimated_cost", "estimated_cost"),
                         ("liability_months", "liability_months"), ("completion_period_days", "completion_period_days")]:
        if f.get(k_src) is not None:
            setattr(w, k_dst, f[k_src])
    actor = user["name"]
    events = []
    if dt == "sanction":
        sd = extraction.to_date(f.get("sanction_date")) or date.today()
        w.proposed_on = w.proposed_on or sd
        w.sanctioned_on = sd
        if new or w.status == "proposed":
            w.status = "sanctioned"
        if f.get("sanction_no"):
            w.reason = f"Administrative approval {f['sanction_no']}"
        events.append(("work_sanctioned", f"Approved: administrative approval {f.get('sanction_no') or ''} for {lakh(w.estimated_cost)} "
                                          f"(from {d.filename})", sd))
    elif dt == "tender":
        w.tendered_on = extraction.to_date(f.get("tender_date")) or date.today()
        if STATUS_ORDER.index(w.status if w.status in STATUS_ORDER else "proposed") < STATUS_ORDER.index("tendered") or new:
            w.status = "tendered"
        events.append(("work_tendered", f"Tender {w.tender_id or ''} extracted from {d.filename} "
                                        f"({lakh(w.estimated_cost)}, liability {w.liability_months or '?'} months)", w.tendered_on))
    elif dt == "award":
        w.awarded_on = extraction.to_date(f.get("award_date")) or date.today()
        w.contractor = f.get("contractor") or w.contractor
        w.awarded_cost = f.get("awarded_cost") or w.awarded_cost
        if w.completion_period_days:
            w.due_on = w.awarded_on + timedelta(days=w.completion_period_days)
        if new or STATUS_ORDER.index(w.status if w.status in STATUS_ORDER else "proposed") < STATUS_ORDER.index("awarded"):
            w.status = "awarded"
        events.append(("work_awarded", f"Awarded to {w.contractor} for {lakh(w.awarded_cost)} (from {d.filename})", w.awarded_on))
    elif dt == "completion":
        if not w.started_on and w.awarded_on:
            w.started_on = w.awarded_on + timedelta(days=10)
            events.append(("work_started", "Work started on site (date assumed: 10 days after the work order)", w.started_on))
        cd = extraction.to_date(f.get("completion_date"))
        if not cd and w.awarded_on and w.completion_period_days:
            cd = w.awarded_on + timedelta(days=w.completion_period_days)
            w.liability_estimated = True
        w.completed_on = cd or date.today()
        w.contractor = f.get("contractor") or w.contractor
        w.status = "completed"
        if w.liability_months:
            w.liability_end = add_months(w.completed_on, w.liability_months)
        asset.status = "in_service"
        session.add(asset)
        events.append(("work_completed", f"Completed by {w.contractor} on {w.completed_on:%d %b %Y}" +
                       (f". Liability clock started: {w.liability_months} months, until {w.liability_end:%d %b %Y}"
                        if w.liability_end else "") + (" (completion date estimated)" if w.liability_estimated else ""), w.completed_on))
    session.add(w)
    session.flush()
    for et, msg, on in events:
        add_event(session, asset.id, et, msg, actor=actor, work_id=w.id, on=on)
    d.status, d.work_id, d.asset_id, d.doc_type = "confirmed", w.id, asset.id, dt
    d.extracted = json.dumps(f)
    session.add(d)
    session.commit()
    ctx = load_ctx(session, user["district"])
    new_flags = [f2 for f2 in compute_flags(ctx) if f2["work_id"] == w.id]
    return {"work": work_dict(w), "created": new, "flags": new_flags}


@app.post("/api/documents/{did}/reject")
def reject_document(did: int, user=Depends(FIELD), session: Session = Depends(get_session)):
    d = session.get(Document, did)
    if not d or d.district != user["district"]:
        raise HTTPException(404)
    d.status = "rejected"
    session.add(d)
    session.commit()
    return {"ok": True}


# ------------------------------------------------------------------ analysis

@app.get("/api/contractors")
def contractors(user=Depends(STAFF), session: Session = Depends(get_session)):
    return contractor_scorecard(load_ctx(session, user["district"]))


@app.get("/api/planner")
def planner(budget_cr: float = 10.0, rural_share: float = 25, user=Depends(require_role("ee", "auditor")),
            session: Session = Depends(get_session)):
    if budget_cr <= 0 or budget_cr > 10000:
        raise HTTPException(400, "Budget must be between 0 and 10,000 crore")
    return budget_plan(load_ctx(session, user["district"]), budget_cr * 1e7, max(0.0, min(100.0, rural_share)) / 100)


@app.get("/api/settings/weights")
def get_weights_api(user=Depends(STAFF), session: Session = Depends(get_session)):
    s = session.get(Setting, "priority_weights")
    return jload(s.value) if s else DEFAULT_WEIGHTS


@app.put("/api/settings/weights")
def put_weights(body: dict = Body(...), user=Depends(EE), session: Session = Depends(get_session)):
    try:
        w = {k: float(body[k]) for k in DEFAULT_WEIGHTS}
    except (KeyError, ValueError):
        raise HTTPException(400, "All five weights are required")
    total = sum(w.values())
    if total <= 0 or any(v < 0 for v in w.values()):
        raise HTTPException(400, "Weights must be positive")
    w = {k: round(v / total, 3) for k, v in w.items()}  # normalise to 1
    s = session.get(Setting, "priority_weights") or Setting(key="priority_weights", value="{}")
    s.value = json.dumps(w)
    session.add(s)
    session.commit()
    return w


@app.get("/api/llm/status")
def llm_status(user=Depends(STAFF)):
    return {"provider": LLM_PROVIDER, "model": LLM_MODEL, "last_error": extraction.LAST_LLM_ERROR["error"]}


@app.post("/api/llm/test")
def llm_test(user=Depends(EE)):
    """Send a short real-format Gujarat tender snippet to the configured LLM and show what comes back."""
    if LLM_PROVIDER == "none":
        return {"ok": False, "provider": "none", "message": "No LLM configured — set OPENROUTER_API_KEY (or LLM_BASE_URL)."}
    sample = ("NOTICE INVITING E-TENDER\nTender ID : 781502\nName of work : Resurfacing of Padra to Karjan Road, "
              "Km. 10/0 to 21/0, Ta. Padra, Dist. Vadodara\nEstimated Cost : Rs. 66,02,418.40\n"
              "Time Limit : 4 (Four) Months\nDefects Liability Period : 3 (Three) years")
    t0 = time.time()
    out = extraction.extract_llm(sample)
    return {"ok": bool(out), "provider": LLM_PROVIDER, "model": LLM_MODEL, "seconds": round(time.time() - t0, 1),
            "fields": out, "error": extraction.LAST_LLM_ERROR["error"]}


@app.post("/api/admin/reset-demo")
def reset_demo(user=Depends(EE)):
    init_db(reset=True)
    with Session(engine) as s:
        seed_if_empty(s, demo=SEED_DEMO)
    return {"ok": True, "message": "Demo data reset"}


# ------------------------------------------------------------------ React single-page app

@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    """Serve the React app for every non-API path (client-side routing)."""
    if full_path.startswith("api/"):
        raise HTTPException(404)
    f = FRONTEND_DIST / full_path
    if full_path and f.is_file() and FRONTEND_DIST.resolve() in f.resolve().parents:
        # hashed build files (assets/index-XXXX.js) never change, so browsers may cache them for a year
        cache = "public, max-age=31536000, immutable" if full_path.startswith("assets/") else "no-cache"
        return FileResponse(f, headers={"Cache-Control": cache})
    index = FRONTEND_DIST / "index.html"
    if not index.exists():
        return HTMLResponse("<h3>Frontend not built.</h3><p>Run <code>cd frontend &amp;&amp; npm install &amp;&amp; npm run build</code>, "
                            "or use <code>npm run dev</code> on port 5173 during development.</p>", status_code=503)
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
