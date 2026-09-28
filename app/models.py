"""Database tables. One asset record; everything else hangs off it."""
from datetime import date, datetime
from typing import Optional

from pydantic import NaiveDatetime
from sqlalchemy import Column, LargeBinary, Text
from sqlmodel import Field, SQLModel


def now() -> datetime:
    return datetime.utcnow()


class Office(SQLModel, table=True):
    """One unit of the R&B hierarchy: department > wing (Chief Engineer) > circle (Superintending Engineer)
    > division (Executive Engineer) > sub-division (Deputy Executive Engineer)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    name: str
    level: str  # department | wing | circle | division | subdivision
    head: str  # designation of the officer in charge
    parent_id: Optional[int] = Field(default=None, index=True)
    talukas: str = ""  # comma separated, for sub-divisions
    onboarded: bool = True  # False = shown in the tree but not on Pravi yet


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    full_name: str
    role: str  # engineer (Deputy EE / AAE) | ee | se | ce | auditor
    district: str = "Vadodara"
    office_id: Optional[int] = Field(default=None, index=True)


class Asset(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    asset_type: str = Field(index=True)  # road_section | bridge | culvert | building
    name: str
    category: str  # SH | MDR | ODR | VR | bridge | culvert | hospital | school | office | quarters
    road_code: Optional[str] = Field(default=None, index=True)
    road_name: Optional[str] = None
    start_km: Optional[float] = None
    end_km: Optional[float] = None
    chainage_km: Optional[float] = None  # for point assets on a road
    lat: Optional[float] = None
    lng: Optional[float] = None
    geometry: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON [[lat,lng],...]
    attrs: str = Field(default="{}", sa_column=Column(Text))  # JSON, type-specific fields
    year_built: Optional[int] = None
    district: str = Field(default="Vadodara", index=True)
    division: str = "Vadodara (R&B)"
    taluka: Optional[str] = None
    office_id: Optional[int] = Field(default=None, index=True)  # the sub-division that maintains it
    status: str = "in_service"  # proposed | under_construction | in_service | closed
    created_at: NaiveDatetime = Field(default_factory=now)


class Work(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    road_code: Optional[str] = Field(default=None, index=True)
    start_km: Optional[float] = None
    end_km: Optional[float] = None
    work_type: str  # new_construction | widening | recarpet | repair | rehab | waterproofing | structural_repair
    title: str
    status: str = Field(default="proposed", index=True)
    # proposed | sanctioned | tendered | awarded | under_construction | completed | cancelled
    contractor: Optional[str] = None
    estimated_cost: Optional[float] = None
    awarded_cost: Optional[float] = None
    tender_id: Optional[str] = Field(default=None, index=True)
    proposed_on: Optional[date] = None
    sanctioned_on: Optional[date] = None
    tendered_on: Optional[date] = None
    awarded_on: Optional[date] = None
    started_on: Optional[date] = None
    due_on: Optional[date] = None
    completed_on: Optional[date] = None
    completion_period_days: Optional[int] = None
    liability_months: Optional[int] = None
    liability_end: Optional[date] = None
    liability_estimated: bool = False  # True when completion date was estimated
    reason: Optional[str] = Field(default=None, sa_column=Column(Text))
    source: str = "manual"  # seed | document | manual
    created_by: Optional[str] = None
    district: str = Field(default="Vadodara", index=True)


class Document(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    work_id: Optional[int] = Field(default=None, foreign_key="work.id", index=True)
    asset_id: Optional[int] = Field(default=None, foreign_key="asset.id", index=True)
    doc_type: str  # tender | award | completion | other
    filename: str
    file_bytes: Optional[bytes] = Field(default=None, sa_column=Column(LargeBinary))
    text: Optional[str] = Field(default=None, sa_column=Column(Text))
    extracted: str = Field(default="{}", sa_column=Column(Text))
    method: str = "rules"  # llm | rules
    confidence: float = 0.0
    status: str = "review"  # review | confirmed | rejected
    uploaded_by: Optional[str] = None
    created_at: NaiveDatetime = Field(default_factory=now)
    district: str = Field(default="Vadodara", index=True)


class Inspection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    kind: str = "inspection"  # inspection | cleaning | structural_audit
    inspected_on: date
    condition: Optional[int] = None  # 1 very poor .. 5 good
    notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    inspector: Optional[str] = None
    photo_id: Optional[int] = None
    safety_class: Optional[str] = None  # structural audits: C1 | C2A | C2B | C3 (Mumbai-style classification)


class Complaint(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ticket: str = Field(index=True, unique=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    lat: float
    lng: float
    km: Optional[float] = None
    issue_type: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    language: str = "en"
    photo_id: Optional[int] = None
    reporter_contact: Optional[str] = None
    report_count: int = 1
    status: str = Field(default="open", index=True)
    # open | verified | assigned | fixed | closed | rejected
    liable_work_id: Optional[int] = None
    liable_contractor: Optional[str] = None
    liable_until: Optional[date] = None
    assigned_kind: Optional[str] = None  # contractor | department
    assigned_to: Optional[str] = None
    condition: Optional[int] = None
    verify_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    fix_notes: Optional[str] = Field(default=None, sa_column=Column(Text))
    fix_photo_id: Optional[int] = None
    fix_lat: Optional[float] = None
    fix_lng: Optional[float] = None
    permit_id: Optional[int] = None  # road was dug under this permit -> the utility must restore it
    source: str = "citizen"  # citizen | patrol
    reopened_count: int = 0
    created_at: NaiveDatetime = Field(default_factory=now)
    updated_at: NaiveDatetime = Field(default_factory=now)
    verified_at: Optional[NaiveDatetime] = None
    assigned_at: Optional[NaiveDatetime] = None
    fixed_at: Optional[NaiveDatetime] = None
    closed_at: Optional[NaiveDatetime] = None
    district: str = Field(default="Vadodara", index=True)


class DigPermit(SQLModel, table=True):
    """Permission for a utility (gas, water, power, telecom) to cut a road. Idea taken from Mumbai's trenching policy."""
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(foreign_key="asset.id", index=True)
    road_code: Optional[str] = Field(default=None, index=True)
    start_km: Optional[float] = None
    end_km: Optional[float] = None
    agency: str
    purpose: str = ""
    length_m: Optional[float] = None
    from_date: date
    to_date: date
    emergency: bool = False
    status: str = Field(default="applied", index=True)  # applied | approved | rejected | restored
    restoration_charge: Optional[float] = None
    decision_note: Optional[str] = Field(default=None, sa_column=Column(Text))
    decided_by: Optional[str] = None
    restored_on: Optional[date] = None
    created_by: Optional[str] = None
    created_at: NaiveDatetime = Field(default_factory=now)
    district: str = Field(default="Vadodara", index=True)


class Photo(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mime: str = "image/jpeg"
    data: bytes = Field(sa_column=Column(LargeBinary))
    created_at: NaiveDatetime = Field(default_factory=now)


class Event(SQLModel, table=True):
    """Append-only history. Rows are only ever inserted, never updated."""
    id: Optional[int] = Field(default=None, primary_key=True)
    asset_id: int = Field(index=True)
    work_id: Optional[int] = None
    complaint_id: Optional[int] = None
    event_type: str
    actor: str = "system"
    message: str = Field(sa_column=Column(Text))
    happened_at: NaiveDatetime = Field(default_factory=now, index=True)


class Setting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str = Field(sa_column=Column(Text))
