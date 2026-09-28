"""The R&B hierarchy: offices, who sees what, who can approve what, and where overdue complaints escalate.

Gujarat R&B (public organisation chart): Secretary > Chief Engineers by wing (State roads, Panchayat roads,
National Highways, ...) > Superintending Engineer (Circle, 3–5 divisions) > Executive Engineer (Division,
usually one district) > Deputy Executive Engineer (Sub-division, usually one or more talukas) >
Additional Assistant Engineer (Section, field staff).
"""
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, Request
from sqlmodel import Session, select

from .models import Asset, Office, User

LEVELS = ["department", "wing", "circle", "division", "subdivision"]
LEVEL_LABEL = {"department": "Department", "wing": "Wing", "circle": "Circle", "division": "Division",
               "subdivision": "Sub-division"}
ROLE_LABEL = {"engineer": "Deputy Executive Engineer", "ee": "Executive Engineer", "se": "Superintending Engineer",
              "ce": "Chief Engineer", "auditor": "Auditor (view only)"}
ROLE_RANK = {"engineer": 1, "ee": 2, "se": 3, "ce": 4, "auditor": 0}
SENIOR = ("ee", "se", "ce")

# Technical-sanction powers (illustrative values; each state notifies its own delegation of powers).
APPROVAL_LIMITS = [("engineer", 5e5), ("ee", 50e5), ("se", 2e7), ("ce", float("inf"))]

# Complaint service levels. Mumbai (BMC) fixes monsoon pothole complaints within 24 h and the
# Bombay High Court (2025) set 48 h as the outer limit; Pravi uses the same idea.
SLA_HOURS = {"pothole": 48, "waterlogging": 48, "railing": 24, "crack": 168, "signage": 168, "leakage": 168,
             "other": 168}
ESCALATION = [(1, "ee"), (3, "se"), (7, "ce")]  # overdue by more than N × SLA -> escalated to this rank
ESCALATION_LABEL = {"engineer": "Sub-division (Deputy Executive Engineer)", "ee": "Executive Engineer",
                    "se": "Superintending Engineer", "ce": "Chief Engineer"}


def is_monsoon(d: date) -> bool:
    return date(d.year, 6, 15) <= d <= date(d.year, 9, 30)


def sla_hours(issue_type: str, reported: datetime) -> int:
    h = SLA_HOURS.get(issue_type, 168)
    if issue_type in ("pothole", "waterlogging") and is_monsoon(reported.date()):
        h = 24
    return h


def complaint_sla(c, now: Optional[datetime] = None) -> dict:
    """How the complaint is doing against its deadline, and who it has escalated to."""
    now = now or datetime.utcnow()
    hours = sla_hours(c.issue_type, c.created_at)
    due = c.created_at + timedelta(hours=hours)
    active = c.status in ("open", "verified", "assigned")
    end = c.fixed_at or c.closed_at or now
    if c.status == "rejected":
        return {"hours": hours, "due": due.isoformat(), "state": "na", "escalated_to": None, "escalation_rank": 0}
    over = (end - c.created_at).total_seconds() / 3600 / hours
    rank = 0
    esc = None
    if active:
        for mult, role in ESCALATION:
            if over > mult:
                rank, esc = ROLE_RANK[role], role
    if active:
        state = "overdue" if now > due else "on_time"
    else:
        state = "met" if end <= due else "missed"
    left_h = (due - now).total_seconds() / 3600
    return {"hours": hours, "due": due.isoformat(), "state": state, "hours_left": round(left_h, 1),
            "escalated_to": esc, "escalated_label": ESCALATION_LABEL.get(esc) if esc else None,
            "escalation_rank": rank}


def approver_for(cost: Optional[float]) -> str:
    c = cost or 0
    for role, limit in APPROVAL_LIMITS:
        if c <= limit:
            return role
    return "ce"


def can_approve(role: str, cost: Optional[float]) -> bool:
    return ROLE_RANK.get(role, 0) >= ROLE_RANK[approver_for(cost)]


# ---------------------------------------------------------------- seed / upgrade

OFFICES = [
    # code, name, level, head, parent, talukas, onboarded
    ("GJ", "Roads & Buildings Department, Gujarat", "department", "Secretary (R&B)", None, "", True),
    ("W-STATE", "State R&B wing", "wing", "Chief Engineer (State R&B)", "GJ", "", True),
    ("W-PANCH", "Panchayat R&B wing", "wing", "Chief Engineer (Panchayat R&B)", "GJ", "", False),
    ("W-NH", "National Highways wing", "wing", "Chief Engineer (NH)", "GJ", "", False),
    ("C-VAD", "Vadodara Circle", "circle", "Superintending Engineer", "W-STATE", "", True),
    ("C-AHD", "Ahmedabad Circle", "circle", "Superintending Engineer", "W-STATE", "", False),
    ("C-SRT", "Surat Circle", "circle", "Superintending Engineer", "W-STATE", "", False),
    ("C-RJT", "Rajkot Circle", "circle", "Superintending Engineer", "W-STATE", "", False),
    ("D-VAD", "Vadodara Division", "division", "Executive Engineer", "C-VAD", "", True),
    ("D-CHU", "Chhota Udaipur Division", "division", "Executive Engineer", "C-VAD", "", False),
    ("D-BRC", "Bharuch Division", "division", "Executive Engineer", "C-VAD", "", False),
    ("D-NAR", "Narmada Division", "division", "Executive Engineer", "C-VAD", "", False),
    ("S-VAD", "Vadodara Sub-division", "subdivision", "Deputy Executive Engineer", "D-VAD",
     "Vadodara,Waghodia,Savli,Desar", True),
    ("S-PAD", "Padra Sub-division", "subdivision", "Deputy Executive Engineer", "D-VAD", "Padra,Karjan,Sinor", True),
    ("S-DAB", "Dabhoi Sub-division", "subdivision", "Deputy Executive Engineer", "D-VAD", "Dabhoi", True),
]

USERS = [
    # username, password, full name, role, office code
    ("ce_state", "Chief@123", "K. Mehta (Chief Engineer, State R&B)", "ce", "W-STATE"),
    ("se_vadodara", "Super@123", "N. Joshi (Superintending Engineer)", "se", "C-VAD"),
    ("ee_vadodara", "Exec@123", "R. Desai (Executive Engineer)", "ee", "D-VAD"),
    ("de_vadodara", "Engineer@123", "A. Patel (Deputy Engineer)", "engineer", "S-VAD"),
    ("de_padra", "Engineer@123", "H. Parmar (Deputy Engineer, Padra)", "engineer", "S-PAD"),
    ("de_dabhoi", "Engineer@123", "S. Vasava (Deputy Engineer, Dabhoi)", "engineer", "S-DAB"),
    ("auditor_vadodara", "Audit@123", "M. Shah (Audit Officer)", "auditor", "D-VAD"),
]


def ensure_hierarchy(session: Session) -> bool:
    """Create the office tree and attach users and assets to it. Safe to run on every start
    (also upgrades a database created before the hierarchy existed)."""
    from .auth import hash_password
    changed = False
    offices = {o.code: o for o in session.exec(select(Office)).all()}
    for code, name, level, head, parent, talukas, onboarded in OFFICES:
        if code in offices:
            continue
        o = Office(code=code, name=name, level=level, head=head, talukas=talukas, onboarded=onboarded,
                   parent_id=offices[parent].id if parent else None)
        session.add(o)
        session.flush()
        offices[code] = o
        changed = True
    users = {u.username: u for u in session.exec(select(User)).all()}
    if users:  # only add the extra hierarchy logins to a database that already has the demo logins
        for username, pw, name, role, office in USERS:
            u = users.get(username)
            if not u:
                session.add(User(username=username, password_hash=hash_password(pw), full_name=name, role=role,
                                 office_id=offices[office].id))
                changed = True
            elif u.office_id is None:
                u.office_id = offices[office].id
                session.add(u)
                changed = True
    for a in session.exec(select(Asset).where(Asset.office_id == None)).all():  # noqa: E711
        a.office_id = subdivision_for(session, a.taluka).id
        session.add(a)
        changed = True
    if changed:
        session.commit()
    return changed


def subdivision_for(session: Session, taluka: Optional[str], fallback_office_id: Optional[int] = None) -> Office:
    subs = session.exec(select(Office).where(Office.level == "subdivision", Office.onboarded == True)).all()  # noqa: E712
    t = (taluka or "").strip().lower()
    for s in subs:
        if t and t in [x.strip().lower() for x in s.talukas.split(",")]:
            return s
    if fallback_office_id:
        o = session.get(Office, fallback_office_id)
        if o and o.level == "subdivision":
            return o
    return sorted(subs, key=lambda s: s.id)[0]


# ---------------------------------------------------------------- scope

def children_map(offices: List[Office]) -> Dict[Optional[int], List[Office]]:
    m: Dict[Optional[int], List[Office]] = {}
    for o in offices:
        m.setdefault(o.parent_id, []).append(o)
    return m


def subtree_ids(offices: List[Office], root_id: int) -> Set[int]:
    kids = children_map(offices)
    out, stack = set(), [root_id]
    while stack:
        i = stack.pop()
        out.add(i)
        stack.extend(o.id for o in kids.get(i, []))
    return out


@dataclass
class Scope:
    office: Office          # the unit currently being viewed
    home: Office            # the user's own office
    office_ids: Set[int]    # every office inside the unit being viewed
    offices: List[Office]   # all offices (for names / tree)
    district: str

    def has(self, asset: Asset) -> bool:
        return asset is not None and asset.office_id in self.office_ids


def get_scope(request: Request, user: dict, session: Session) -> Scope:
    offices = session.exec(select(Office)).all()
    if not offices:
        ensure_hierarchy(session)
        offices = session.exec(select(Office)).all()
    u = session.get(User, int(user["sub"])) if str(user.get("sub", "")).isdigit() else None
    home = next((o for o in offices if u and o.id == u.office_id), None) \
        or next(o for o in offices if o.code == "D-VAD")
    allowed = subtree_ids(offices, home.id)
    view = home
    want = request.headers.get("x-pravi-office")
    if want and want.isdigit() and int(want) in allowed:
        view = next(o for o in offices if o.id == int(want))
    return Scope(office=view, home=home, office_ids=subtree_ids(offices, view.id), offices=offices,
                 district=user.get("district") or "Vadodara")


def office_brief(o: Office) -> dict:
    return {"id": o.id, "code": o.code, "name": o.name, "level": o.level, "level_label": LEVEL_LABEL[o.level],
            "head": o.head, "parent_id": o.parent_id, "onboarded": o.onboarded,
            "talukas": [t for t in o.talukas.split(",") if t]}


def breadcrumb(offices: List[Office], office: Office) -> List[dict]:
    by_id = {o.id: o for o in offices}
    chain, cur = [], office
    while cur:
        chain.append(office_brief(cur))
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return list(reversed(chain))


def unit_of(offices: List[Office], office_id: Optional[int], parent_id: int) -> Optional[int]:
    """Which direct child of `parent_id` contains `office_id`."""
    by_id = {o.id: o for o in offices}
    cur = by_id.get(office_id)
    while cur and cur.parent_id != parent_id:
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return cur.id if cur else None
