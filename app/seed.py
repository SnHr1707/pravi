"""Demo data for Vadodara district (R&B).

All dates are relative to today so the planted cases stay valid whenever the
app is started. Road geometry is hand-traced and approximate; road codes,
contractors and figures are illustrative (fictional) demo data.
"""
import json
from datetime import date, datetime, time, timedelta

from sqlmodel import Session, select

from .auth import hash_password
from .geo import point_at, slice_polyline
from .models import Asset, Complaint, Document, Event, Inspection, Setting, User, Work
from .rules import DEFAULT_WEIGHTS, add_months

D = "Vadodara"

ROADS = [
    dict(code="SH-VP", name="Vadodara–Padra–Jambusar Road", cat="SH", km=48, taluka="Padra",
         pts=[(22.3072, 73.1812), (22.2985, 73.1560), (22.2800, 73.1250), (22.2600, 73.1020), (22.2385, 73.0850),
              (22.2050, 73.0300), (22.1600, 72.9600), (22.1100, 72.8800), (22.0540, 72.8090)],
         sections=[(0, 16), (16, 32), (32, 48)], width=10, lanes="2-lane with paved shoulders", traffic=14500),
    dict(code="SH-VD", name="Vadodara–Dabhoi Road", cat="SH", km=29, taluka="Dabhoi",
         pts=[(22.3072, 73.1812), (22.2900, 73.2250), (22.2600, 73.2800), (22.2350, 73.3350), (22.2100, 73.3850),
              (22.1837, 73.4290)],
         sections=[(0, 15), (15, 29)], width=10, lanes="2-lane", traffic=16800),
    dict(code="SH-VS", name="Vadodara–Savli Road", cat="SH", km=29, taluka="Savli",
         pts=[(22.3072, 73.1812), (22.3500, 73.1900), (22.4000, 73.2000), (22.4600, 73.2050), (22.5150, 73.2150),
              (22.5667, 73.2200)],
         sections=[(0, 15), (15, 29)], width=7, lanes="2-lane (being widened)", traffic=12100),
    dict(code="MDR-VW", name="Vadodara–Waghodia Road", cat="MDR", km=22, taluka="Waghodia",
         pts=[(22.3072, 73.1812), (22.3100, 73.2350), (22.3080, 73.2900), (22.3060, 73.3450), (22.3050, 73.4000)],
         sections=[(0, 11), (11, 22)], width=7, lanes="2-lane", traffic=9400),
    dict(code="MDR-KS", name="Karjan–Sinor Road", cat="MDR", km=27, taluka="Karjan",
         pts=[(22.0530, 73.1235), (22.0300, 73.1700), (22.0000, 73.2200), (21.9600, 73.2750), (21.9140, 73.3390)],
         sections=[(0, 13), (13, 27)], width=7, lanes="2-lane", traffic=6200),
    dict(code="ODR-PK", name="Padra–Karjan Road", cat="ODR", km=21, taluka="Padra",
         pts=[(22.2385, 73.0850), (22.2000, 73.0950), (22.1500, 73.1050), (22.1000, 73.1150), (22.0530, 73.1235)],
         sections=[(0, 10), (10, 21)], width=5.5, lanes="Intermediate lane", traffic=3100),
    dict(code="VR-DS", name="Dabhoi–Sinor Village Road", cat="VR", km=31, taluka="Dabhoi",
         pts=[(22.1837, 73.4290), (22.1300, 73.4100), (22.0700, 73.3850), (22.0000, 73.3650), (21.9140, 73.3390)],
         sections=[(0, 15), (15, 31)], width=3.75, lanes="Single lane", traffic=900),
]

CONTRACTORS = ["Aarav Roadways", "Kesar Infra Works", "Neel Buildcon", "Saptarshi Constructions",
               "Tapi Line Engineering", "Vihaan Infra Projects", "Mahisagar Civil Works"]


def seed_if_empty(session: Session, demo: bool = True) -> bool:
    if session.exec(select(User)).first():
        return False
    if demo:
        seed(session)
    else:
        seed_users(session)
        session.commit()
    return True


def seed_users(session: Session):
    for u, pw, name, role in [
        ("de_vadodara", "Engineer@123", "A. Patel (Deputy Engineer)", "engineer"),
        ("ee_vadodara", "Exec@123", "R. Desai (Executive Engineer)", "ee"),
        ("auditor_vadodara", "Audit@123", "M. Shah (Audit Officer)", "auditor"),
    ]:
        session.add(User(username=u, password_hash=hash_password(pw), full_name=name, role=role, district=D))
    session.add(Setting(key="priority_weights", value=json.dumps(DEFAULT_WEIGHTS)))


def seed(session: Session, today: date = None):
    T = today or date.today()

    def d(days_ago: int) -> date:
        return T - timedelta(days=days_ago)

    def at(day: date, hour: int = 10) -> datetime:
        return datetime.combine(day, time(hour, 0))

    def ev(asset, etype, msg, when, actor="system", work=None, complaint=None):
        session.add(Event(asset_id=asset.id, work_id=work.id if work else None,
                          complaint_id=complaint.id if complaint else None,
                          event_type=etype, actor=actor, message=msg, happened_at=when))

    # ---------------- users
    seed_users(session)

    # ---------------- road sections
    road_pts = {}
    sec = {}
    n = 0
    for r in ROADS:
        road_pts[r["code"]] = r["pts"]
        for s0, s1 in r["sections"]:
            n += 1
            geom = slice_polyline(r["pts"], s0 / r["km"], s1 / r["km"])
            mid = geom[len(geom) // 2]
            a = Asset(code=f"VAD-RS-{n:03d}", asset_type="road_section", category=r["cat"],
                      name=f"{r['code']} {r['name']}, km {s0}–{s1}", road_code=r["code"], road_name=r["name"],
                      start_km=s0, end_km=s1, lat=mid[0], lng=mid[1], geometry=json.dumps(geom),
                      attrs=json.dumps({"surface": "Bituminous (BC)", "carriageway_width_m": r["width"],
                                        "lanes": r["lanes"], "traffic_pcu_day": r["traffic"],
                                        "road_total_km": r["km"]}),
                      year_built=1985 + n % 20, district=D, taluka=r["taluka"])
            session.add(a)
            session.flush()
            sec[(r["code"], s0)] = a
            ev(a, "registered", f"Registered in inventory: {a.name}", at(d(4000)))

    def road_point(code, km):
        r = next(x for x in ROADS if x["code"] == code)
        return point_at(r["pts"], km / r["km"])

    def section_for(code, km):
        r = next(x for x in ROADS if x["code"] == code)
        for s0, s1 in r["sections"]:
            if s0 <= km <= s1:
                return sec[(code, s0)]

    # ---------------- bridges, culverts
    def point_asset(code, atype, cat, name, road, km, year, attrs, taluka):
        lat, lng = road_point(road, km)
        rc = next(x for x in ROADS if x["code"] == road)["cat"]
        a = Asset(code=code, asset_type=atype, category=cat, name=name, road_code=road,
                  road_name=next(x for x in ROADS if x["code"] == road)["name"], chainage_km=km,
                  lat=lat, lng=lng, attrs=json.dumps({"road_category": rc, **attrs}), year_built=year,
                  district=D, taluka=taluka)
        session.add(a)
        session.flush()
        ev(a, "registered", f"Registered in inventory: {a.name}", at(d(4000)))
        return a

    br1 = point_asset("VAD-BR-001", "bridge", "bridge", "Vishwamitri River Bridge (SH-VP km 3.5)", "SH-VP", 3.5, 1978,
                      {"type": "RCC T-beam", "spans": "6 × 20 m", "length_m": 120, "load_class": "IRC Class A"}, "Vadodara")
    br2 = point_asset("VAD-BR-002", "bridge", "bridge", "Dhadhar River Bridge (MDR-KS km 8)", "MDR-KS", 8, 1989,
                      {"type": "PSC box girder", "spans": "4 × 30 m", "length_m": 120, "load_class": "IRC Class A"}, "Karjan")
    br3 = point_asset("VAD-BR-003", "bridge", "bridge", "Orsang River Bridge (VR-DS km 20)", "VR-DS", 20, 1992,
                      {"type": "RCC slab", "spans": "8 × 12 m", "length_m": 96, "load_class": "IRC Class A"}, "Dabhoi")
    br4 = point_asset("VAD-BR-004", "bridge", "bridge", "Mini River Bridge (SH-VS km 12)", "SH-VS", 12, 2008,
                      {"type": "PSC girder", "spans": "3 × 25 m", "length_m": 75, "load_class": "IRC 70R"}, "Savli")

    cu1 = point_asset("VAD-CU-001", "culvert", "culvert", "Box culvert, SH-VD km 6.2", "SH-VD", 6.2, 2001,
                      {"type": "RCC box", "size": "2 × 2 m"}, "Vadodara")
    cu2 = point_asset("VAD-CU-002", "culvert", "culvert", "Pipe culvert, SH-VD km 11.8", "SH-VD", 11.8, 1996,
                      {"type": "Hume pipe", "size": "2 × 1.2 m dia"}, "Dabhoi")
    cu3 = point_asset("VAD-CU-003", "culvert", "culvert", "Slab culvert, MDR-VW km 7.4", "MDR-VW", 7.4, 2024,
                      {"type": "RCC slab", "size": "3 m span"}, "Waghodia")
    cu4 = point_asset("VAD-CU-004", "culvert", "culvert", "Pipe culvert, ODR-PK km 14.1", "ODR-PK", 14.1, 1999,
                      {"type": "Hume pipe", "size": "1 × 0.9 m dia"}, "Padra")
    cu5 = point_asset("VAD-CU-005", "culvert", "culvert", "Box culvert, SH-VP km 26.5", "SH-VP", 26.5, 2010,
                      {"type": "RCC box", "size": "2 × 1.5 m"}, "Padra")

    def building(code, cat, name, lat, lng, year, attrs, taluka):
        a = Asset(code=code, asset_type="building", category=cat, name=name, lat=lat, lng=lng,
                  attrs=json.dumps(attrs), year_built=year, district=D, taluka=taluka)
        session.add(a)
        session.flush()
        ev(a, "registered", f"Registered in inventory: {a.name}", at(d(4000)))
        return a

    bl1 = building("VAD-BL-001", "hospital", "District Civil Hospital – Block B", 22.3125, 73.1905, 1985,
                   {"user_department": "Health & Family Welfare", "floors": 4, "floor_area_sqm": 6400, "beds": 220, "daily_users": 1500}, "Vadodara")
    bl2 = building("VAD-BL-002", "school", "Government Secondary School, Karjan", 22.0555, 73.1210, 1998,
                   {"user_department": "Education", "floors": 2, "floor_area_sqm": 2100, "students": 750, "daily_users": 800}, "Karjan")
    bl3 = building("VAD-BL-003", "office", "Taluka Seva Sadan, Dabhoi", 22.1860, 73.4265, 2004,
                   {"user_department": "Revenue", "floors": 3, "floor_area_sqm": 3300, "daily_users": 400}, "Dabhoi")
    bl4 = building("VAD-BL-004", "quarters", "R&B Staff Quarters (Type-B), Vadodara", 22.3150, 73.1700, 1979,
                   {"user_department": "Roads & Buildings", "floors": 3, "units": 24, "floor_area_sqm": 1900, "daily_users": 90}, "Vadodara")

    # ---------------- works
    tender_seq = [140]

    def work(asset, wtype, title, status, contractor=None, est=None, awarded=None, k0=None, k1=None,
             proposed=None, sanctioned=None, tendered=None, awarded_on=None, started=None, due=None,
             completed=None, liability=None, reason=None, tid=None):
        tender_seq[0] += 1
        fy = (tendered or proposed or T).year
        tid = tid or (f"RNB/VAD/{fy}/{tender_seq[0]:04d}" if tendered else None)
        w = Work(asset_id=asset.id, road_code=asset.road_code if asset.asset_type == "road_section" else None,
                 start_km=k0, end_km=k1, work_type=wtype, title=title, status=status, contractor=contractor,
                 estimated_cost=est, awarded_cost=awarded, tender_id=tid, proposed_on=proposed,
                 sanctioned_on=sanctioned, tendered_on=tendered, awarded_on=awarded_on, started_on=started,
                 due_on=due, completed_on=completed, liability_months=liability,
                 liability_end=add_months(completed, liability) if (completed and liability) else None,
                 reason=reason, source="seed", created_by="seed", district=D)
        session.add(w)
        session.flush()
        steps = [(proposed, "proposed", f"Proposed: {title}" + (f" — {reason}" if reason else "")),
                 (sanctioned, "sanctioned", f"Sanctioned by Executive Engineer (est. ₹{(est or 0) / 1e5:.1f} lakh)"),
                 (tendered, "tendered", f"Tender {tid} published"),
                 (awarded_on, "awarded", f"Awarded to {contractor} for ₹{(awarded or 0) / 1e5:.1f} lakh"),
                 (started, "started", "Work started on site"),
                 (completed, "completed", f"Completed by {contractor}. Defect liability {liability} months, until "
                                          f"{w.liability_end:%d %b %Y}" if completed and liability else "Completed")]
        for day, et, msg in steps:
            if day:
                ev(asset, "work_" + et, msg, at(day), actor="R&B Vadodara", work=w)
        return w

    # A. SH-VP km 16–32: re-carpeted 18 months ago (36-month liability) — then a paid patch tender on it.
    A = sec[("SH-VP", 16)]
    wA = work(A, "recarpet", "Re-carpeting of SH-VP km 16.0 to 32.0 (40 mm BC)", "completed", CONTRACTORS[0],
              est=2.45e7, awarded=2.31e7, k0=16, k1=32, proposed=d(900), sanctioned=d(860), tendered=d(820),
              awarded_on=d(780), started=d(760), due=d(560), completed=d(548), liability=36)
    work(A, "repair", "Patch repair of potholes on SH-VP km 20.0 to 24.0", "tendered", None,
         est=1.85e6, k0=20, k1=24, proposed=d(40), sanctioned=d(32), tendered=d(25),
         reason="Potholes after monsoon")
    for tag, day, doc_type in [("tender", d(820), "tender"), ("award", d(780), "award"), ("completion", d(548), "completion")]:
        session.add(Document(work_id=wA.id, asset_id=A.id, doc_type=doc_type, filename=f"{wA.tender_id.replace('/', '_')}_{tag}.pdf",
                             extracted=json.dumps({"tender_id": wA.tender_id, "contractor": wA.contractor,
                                                   "liability_months": 36, "start_km": 16, "end_km": 32}),
                             method="seed", confidence=1.0, status="confirmed", uploaded_by="seed",
                             created_at=at(day), district=D))
    work(sec[("SH-VP", 0)], "recarpet", "Re-carpeting of SH-VP km 0.0 to 16.0", "completed", CONTRACTORS[2],
         est=2.2e7, awarded=2.05e7, k0=0, k1=16, proposed=d(1500), sanctioned=d(1460), tendered=d(1430),
         awarded_on=d(1400), started=d(1380), due=d(1200), completed=d(1190), liability=24)
    work(sec[("SH-VP", 32)], "recarpet", "Re-carpeting of SH-VP km 32.0 to 48.0", "proposed", None,
         est=2.6e7, k0=32, k1=48, proposed=d(12), reason="Surface ravelling; last renewed 6 years ago")

    # B. SH-VD km 0–15: old surface, patched again and again.
    B = sec[("SH-VD", 0)]
    work(B, "recarpet", "Re-carpeting of SH-VD km 0.0 to 15.0", "completed", CONTRACTORS[1],
         est=1.9e7, awarded=1.76e7, k0=0, k1=15, proposed=d(3300), sanctioned=d(3260), tendered=d(3230),
         awarded_on=d(3200), started=d(3180), due=d(3050), completed=d(3080), liability=12)
    for i, (k0, k1, days, cost) in enumerate([(3, 5, 330, 5.4e5), (8, 10, 190, 4.8e5), (4, 7, 120, 6.2e5)]):
        work(B, "repair", f"Patch repair on SH-VD km {k0:.1f} to {k1:.1f}", "completed", CONTRACTORS[2],
             est=cost * 1.05, awarded=cost, k0=k0, k1=k1, proposed=d(days + 30), sanctioned=d(days + 25),
             tendered=d(days + 20), awarded_on=d(days + 12), started=d(days + 8), completed=d(days), liability=3)
    work(sec[("SH-VD", 15)], "recarpet", "Re-carpeting of SH-VD km 15.0 to 29.0", "completed", CONTRACTORS[4],
         est=1.8e7, awarded=1.7e7, k0=15, k1=29, proposed=d(1700), sanctioned=d(1660), tendered=d(1630),
         awarded_on=d(1600), started=d(1580), due=d(1420), completed=d(1410), liability=36)

    # C. SH-VS km 15–29 widening running late; km 0–15 renewed 2.5 years ago.
    work(sec[("SH-VS", 15)], "widening", "Widening of SH-VS km 15.0 to 29.0 from 7 m to 10 m", "under_construction",
         CONTRACTORS[3], est=6.8e7, awarded=6.45e7, k0=15, k1=29, proposed=d(700), sanctioned=d(640),
         tendered=d(560), awarded_on=d(480), started=d(450), due=d(90), tid="RNB/VAD/2025/0150")
    work(sec[("SH-VS", 0)], "recarpet", "Re-carpeting of SH-VS km 0.0 to 15.0", "completed", CONTRACTORS[5],
         est=2.0e7, awarded=1.92e7, k0=0, k1=15, proposed=d(1150), sanctioned=d(1110), tendered=d(1080),
         awarded_on=d(1040), started=d(1020), due=d(900), completed=d(910), liability=36)

    # D. MDR-VW km 0–11: new road whose 24-month liability ends in ~2 months.
    wD = work(sec[("MDR-VW", 0)], "new_construction", "Construction of 2-lane MDR-VW km 0.0 to 11.0", "completed",
              CONTRACTORS[5], est=4.4e7, awarded=4.21e7, k0=0, k1=11, proposed=d(1300), sanctioned=d(1240),
              tendered=d(1180), awarded_on=d(1120), started=d(1100), due=d(700), completed=d(680), liability=24)
    work(sec[("MDR-VW", 11)], "recarpet", "Re-carpeting of MDR-VW km 11.0 to 22.0", "completed", CONTRACTORS[6],
         est=1.1e7, awarded=1.04e7, k0=11, k1=22, proposed=d(2100), sanctioned=d(2060), tendered=d(2030),
         awarded_on=d(2000), started=d(1980), due=d(1880), completed=d(1870), liability=12)

    # E. MDR-KS km 0–13: rehabilitated 23 months ago (36 months) — a paid repair was awarded anyway.
    E = sec[("MDR-KS", 0)]
    work(E, "rehab", "Strengthening and rehabilitation of MDR-KS km 0.0 to 13.0", "completed", CONTRACTORS[4],
         est=3.1e7, awarded=2.94e7, k0=0, k1=13, proposed=d(1200), sanctioned=d(1150), tendered=d(1100),
         awarded_on=d(1050), started=d(1030), due=d(720), completed=d(700), liability=36)
    work(E, "repair", "Special repairs to MDR-KS km 3.0 to 7.0", "awarded", CONTRACTORS[2],
         est=9.6e5, awarded=9.2e5, k0=3, k1=7, proposed=d(75), sanctioned=d(66), tendered=d(55), awarded_on=d(20),
         due=d(-40), reason="Surface cracking reported")
    work(E, "widening", "Widening of MDR-KS km 8.0 to 13.0 to 10 m", "proposed", None, est=3.9e7, k0=8, k1=13,
         proposed=d(10), reason="Traffic growth towards Sinor")
    work(sec[("MDR-KS", 13)], "recarpet", "Re-carpeting of MDR-KS km 13.0 to 27.0", "completed", CONTRACTORS[6],
         est=1.4e7, awarded=1.33e7, k0=13, k1=27, proposed=d(1650), sanctioned=d(1610), tendered=d(1580),
         awarded_on=d(1550), started=d(1530), due=d(1420), completed=d(1430), liability=24)

    # F. ODR-PK: km 10–21 last renewed 9 years ago.
    work(sec[("ODR-PK", 10)], "recarpet", "Re-carpeting of ODR-PK km 10.0 to 21.0", "completed", CONTRACTORS[1],
         est=6.5e6, awarded=6.1e6, k0=10, k1=21, proposed=d(3500), sanctioned=d(3450), tendered=d(3420),
         awarded_on=d(3400), started=d(3390), due=d(3300), completed=d(3290), liability=12)
    work(sec[("ODR-PK", 0)], "recarpet", "Re-carpeting of ODR-PK km 0.0 to 10.0", "completed", CONTRACTORS[6],
         est=5.8e6, awarded=5.5e6, k0=0, k1=10, proposed=d(1500), sanctioned=d(1460), tendered=d(1430),
         awarded_on=d(1410), started=d(1400), due=d(1320), completed=d(1310), liability=24)

    # G. VR-DS: scheme road; resurfacing of km 15–31 sanctioned.
    work(sec[("VR-DS", 0)], "new_construction", "Construction of village road VR-DS km 0.0 to 15.0", "completed",
         CONTRACTORS[6], est=2.4e7, awarded=2.28e7, k0=0, k1=15, proposed=d(1800), sanctioned=d(1760),
         tendered=d(1720), awarded_on=d(1690), started=d(1670), due=d(1480), completed=d(1460), liability=60)
    work(sec[("VR-DS", 15)], "recarpet", "Resurfacing of VR-DS km 15.0 to 31.0", "sanctioned", None,
         est=1.2e7, k0=15, k1=31, proposed=d(60), sanctioned=d(20), reason="Surface failures after monsoon")

    # Older renewals (history for the remaining sections)
    work(sec[("SH-VP", 32)], "recarpet", "Re-carpeting of SH-VP km 32.0 to 48.0 (2020)", "completed", CONTRACTORS[3],
         est=1.9e7, awarded=1.81e7, k0=32, k1=48, proposed=d(2400), sanctioned=d(2370), tendered=d(2340),
         awarded_on=d(2310), started=d(2300), due=d(2200), completed=d(2210), liability=24)
    work(sec[("SH-VS", 15)], "recarpet", "Re-carpeting of SH-VS km 15.0 to 29.0 (2018)", "completed", CONTRACTORS[1],
         est=1.2e7, awarded=1.13e7, k0=15, k1=29, proposed=d(3000), sanctioned=d(2970), tendered=d(2950),
         awarded_on=d(2930), started=d(2920), due=d(2850), completed=d(2860), liability=12)
    work(sec[("VR-DS", 15)], "new_construction", "Construction of village road VR-DS km 15.0 to 31.0 (PMGSY-style scheme)",
         "completed", CONTRACTORS[6], est=1.9e7, awarded=1.8e7, k0=15, k1=31, proposed=d(3900), sanctioned=d(3870),
         tendered=d(3840), awarded_on=d(3810), started=d(3800), due=d(3650), completed=d(3660), liability=60)

    # Bridges / buildings
    work(br2, "rehab", "Rehabilitation of Dhadhar River Bridge (bearings, expansion joints)", "completed",
         CONTRACTORS[5], est=1.6e7, awarded=1.52e7, proposed=d(1000), sanctioned=d(960), tendered=d(920),
         awarded_on=d(880), started=d(860), due=d(760), completed=d(730), liability=60)
    work(bl1, "waterproofing", "Terrace waterproofing, Civil Hospital Block B", "completed", CONTRACTORS[1],
         est=2.2e6, awarded=2.05e6, proposed=d(560), sanctioned=d(540), tendered=d(520), awarded_on=d(500),
         started=d(490), due=d(430), completed=d(425), liability=12)
    for days, cost in [(300, 3.1e5), (150, 2.7e5), (45, 3.4e5)]:
        work(bl1, "repair", "Leakage repairs, Civil Hospital Block B", "completed", CONTRACTORS[0],
             est=cost, awarded=cost, proposed=d(days + 20), sanctioned=d(days + 15), tendered=d(days + 12),
             awarded_on=d(days + 8), started=d(days + 5), completed=d(days), liability=3)
    work(bl4, "structural_repair", "Structural repairs to staff quarters (columns, slabs)", "proposed", None,
         est=8.5e6, proposed=d(30), reason="Spalling concrete, exposed reinforcement")

    # ---------------- inspections
    def insp(asset, days, cond, notes, kind="inspection", who="A. Patel"):
        i = Inspection(asset_id=asset.id, kind=kind, inspected_on=d(days), condition=cond, notes=notes, inspector=who)
        session.add(i)
        label = {"inspection": "Inspection", "cleaning": "Cleaning", "structural_audit": "Structural audit"}[kind]
        ev(asset, kind, f"{label}: " + (f"condition {cond}/5. " if cond else "") + notes, at(d(days), 11), actor=who)

    for (code, s0), days, cond, note in [
        (("SH-VP", 0), 180, 4, "Surface fair, minor edge breaks"),
        (("SH-VP", 16), 35, 3, "Potholes at km 20–24, ravelling in patches"),
        (("SH-VP", 32), 360, 3, "Ravelling, hairline cracks"),
        (("SH-VD", 0), 400, 3, "Cracking at several locations"),
        (("SH-VD", 0), 60, 2, "Extensive potholes and alligator cracking km 3–10; patches failing"),
        (("SH-VD", 15), 200, 3, "Fair, some cracks"),
        (("SH-VS", 0), 150, 4, "Good"),
        (("SH-VS", 15), 90, 3, "Work zone; diversion surface poor"),
        (("MDR-VW", 0), 120, 4, "Good, a few cracks near km 6"),
        (("MDR-VW", 11), 300, 3, "Fair"),
        (("MDR-KS", 0), 80, 3, "Surface cracking km 3–7 on a road rehabilitated two years ago"),
        (("MDR-KS", 13), 260, 4, "Good"),
        (("ODR-PK", 0), 240, 3, "Fair"),
        (("ODR-PK", 10), 100, 2, "Surface worn out, potholes"),
        (("VR-DS", 0), 210, 3, "Fair"),
        (("VR-DS", 15), 95, 2, "Surface failures after monsoon"),
    ]:
        insp(sec[(code, s0)], days, cond, note)
    insp(br1, 430, 2, "Cracks in deck slab and girders, bearings corroded, railing damaged", who="Bridge cell")
    insp(br2, 95, 4, "Post-rehab: joints and bearings fine", who="Bridge cell")
    insp(br3, 250, 3, "Scour near pier P3, wearing coat damaged", who="Bridge cell")
    insp(br4, 60, 4, "Good", who="Bridge cell")
    season = date(T.year if T >= date(T.year, 6, 15) else T.year - 1, 5, 1)
    insp(cu1, (T - (season + timedelta(days=10))).days, None, "Silt removed before monsoon", kind="cleaning")
    insp(cu2, (T - (season - timedelta(days=365))).days, None, "Cleaned (previous season)", kind="cleaning")
    insp(cu3, (T - (season + timedelta(days=20))).days, None, "Silt removed before monsoon", kind="cleaning")
    insp(cu4, (T - (season - timedelta(days=730))).days, None, "Cleaned", kind="cleaning")
    insp(cu5, (T - (season + timedelta(days=5))).days, None, "Silt removed before monsoon", kind="cleaning")
    insp(bl1, 7 * 365 + 40, 3, "Seepage in terrace slab, cracks in partition walls", kind="structural_audit", who="GERI Vadodara")
    insp(bl2, 2 * 365, 3, "Minor cracks; roof needs waterproofing", kind="structural_audit", who="GERI Vadodara")
    insp(bl3, 3 * 365, 4, "Good", kind="structural_audit", who="GERI Vadodara")
    insp(bl4, 9 * 365, 2, "Spalling of column concrete, corroded bars", kind="structural_audit", who="GERI Vadodara")
    session.flush()

    # ---------------- complaints
    seq = [10240]

    def complaint(asset, road, km, issue, desc, count, status, created_days, lang="en",
                  verified_days=None, assigned_days=None, assigned_kind=None, fixed_days=None, closed_days=None,
                  point=None):
        seq[0] += 1
        lat, lng = point or road_point(road, km)
        c = Complaint(ticket=f"GJ-VAD-{seq[0]}", asset_id=asset.id, lat=lat, lng=lng, km=km, issue_type=issue,
                      description=desc, language=lang, report_count=count, status=status,
                      created_at=at(d(created_days), 9), updated_at=at(d(min(x for x in [created_days, verified_days,
                                                                                         assigned_days, fixed_days, closed_days] if x is not None)), 12),
                      district=D)
        # liability check at the reported spot
        from .rules import liability_windows, load_ctx
        ctx = load_ctx(session, D, today=d(created_days))
        wins = liability_windows(ctx, ctx.assets[asset.id], km, km, on=d(created_days)) if asset.asset_type == "road_section" \
            else liability_windows(ctx, ctx.assets[asset.id], on=d(created_days))
        if wins:
            c.liable_work_id, c.liable_contractor, c.liable_until = wins[0].id, wins[0].contractor, wins[0].liability_end
        session.add(c)
        session.flush()
        where = f"{road} km {km:g}" if road and km is not None else asset.name
        ev(asset, "complaint_reported", f"Citizen reported {issue} at {where} ({c.ticket})"
           + (f" — {count} reports merged" if count > 1 else ""), c.created_at, actor="Citizen", complaint=c)
        if c.liable_contractor:
            ev(asset, "liability_check", f"Under liability: {c.liable_contractor} until {c.liable_until:%d %b %Y}",
               c.created_at + timedelta(minutes=1), complaint=c)
        if verified_days is not None:
            c.verified_at = at(d(verified_days), 15)
            c.condition = 2
            ev(asset, "complaint_verified", f"{c.ticket} verified on site by A. Patel", c.verified_at, actor="A. Patel", complaint=c)
        if assigned_days is not None:
            c.assigned_at = at(d(assigned_days), 16)
            c.assigned_kind = assigned_kind
            c.assigned_to = c.liable_contractor if assigned_kind == "contractor" else "Department maintenance gang"
            msg = (f"Defect notice issued to {c.assigned_to} (liable until {c.liable_until:%d %b %Y}) — ₹0 to department"
                   if assigned_kind == "contractor" else f"{c.ticket} assigned to {c.assigned_to}")
            ev(asset, "complaint_assigned", msg, c.assigned_at, actor="R. Desai", complaint=c)
        if fixed_days is not None:
            c.fixed_at = at(d(fixed_days), 17)
            c.fix_notes = "Repaired"
            ev(asset, "complaint_fixed", f"{c.ticket} marked fixed with photo", c.fixed_at, actor="A. Patel", complaint=c)
        if closed_days is not None:
            c.closed_at = at(d(closed_days), 18)
            ev(asset, "complaint_closed", f"Citizen confirmed fix; {c.ticket} closed", c.closed_at, actor="Citizen", complaint=c)
        session.add(c)
        return c

    complaint(A, "SH-VP", 22.1, "pothole", "Big potholes near the bus stop, two-wheelers falling", 7, "assigned", 24,
              verified_days=21, assigned_days=19, assigned_kind="contractor")
    complaint(A, "SH-VP", 23.4, "crack", "Cracks across the road", 2, "open", 1, lang="gu")
    complaint(B, "SH-VD", 4.8, "pothole", "Road full of potholes after rain", 9, "verified", 14, verified_days=11)
    complaint(B, "SH-VD", 9.3, "pothole", "Potholes near the village turning", 4, "assigned", 8, verified_days=6,
              assigned_days=5, assigned_kind="department")
    complaint(cu2, "SH-VD", 11.8, "waterlogging", "Water stands on the road for days after rain", 5, "open", 3, lang="hi")
    complaint(B, "SH-VD", 2.0, "signage", "Speed-breaker sign board fallen", 1, "fixed", 9, verified_days=8,
              assigned_days=7, assigned_kind="department", fixed_days=1)
    complaint(E, "MDR-KS", 5.2, "crack", "Road surface cracking and breaking", 3, "assigned", 6, verified_days=4,
              assigned_days=3, assigned_kind="contractor")
    complaint(sec[("MDR-VW", 0)], "MDR-VW", 6.0, "crack", "Cracks on new road", 1, "open", 2)
    complaint(sec[("ODR-PK", 10)], "ODR-PK", 15.0, "pothole", "Potholes", 6, "closed", 40, verified_days=38,
              assigned_days=36, assigned_kind="department", fixed_days=24, closed_days=22)
    complaint(sec[("VR-DS", 15)], "VR-DS", 22.0, "pothole", "Road broken near Orsang bridge approach", 3, "open", 4, lang="gu")
    complaint(br1, "SH-VP", 3.5, "railing", "Bridge railing broken, dangerous at night", 4, "verified", 16, verified_days=13)
    complaint(bl1, None, None, "leakage", "Roof leaking in ward 7", 3, "assigned", 9, verified_days=8,
              assigned_days=6, assigned_kind="department", point=(bl1.lat, bl1.lng))
    complaint(sec[("SH-VS", 15)], "SH-VS", 20.0, "other", "Diversion road dusty and broken during widening", 2, "open", 5)
    complaint(sec[("SH-VP", 0)], "SH-VP", 5.0, "other", "Street light not working", 1, "rejected", 30)
    session.flush()
    session.commit()
