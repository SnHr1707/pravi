"""Checks the rule-based reader against wording from real, public Gujarat R&B documents.

Run:  python -m pytest -q   (or: python tests/test_extraction.py)

Sources (public web pages, quoted only in part):
- Form B-1 (GARUD, Gujarat): https://www.garud.org.in/wp-content/uploads/2020/07/B-1-Technical-Bid.pdf
- R&B tender titles listed at: https://www.tendersontime.com/authority/roads-and-buildings-department-govt-of-gujarat-tenders-3586/
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.extraction import extract_rules, parse_chainage  # noqa: E402

REAL_B1 = """FORM B-1
GUJARAT STATE ROADS & BUILDING DEPARTMENT /
WATER RESOURCES DEPARTMENT
PERCENTAGE RATE TENDER AND CONTRACT FOR WORKS
Name of work :- Tender For Development of Parking at The Hotel Leela Gandhinagar.
MEMORANDUM OF WORKS IN BRIEF
(2) Estimated Cost – Rs. 2,61,39,631.52
(3) Earnest Money – Rs. 2,61,396.31
(6) Time allowed for completion – 75 (Seventy Five) Days from the date of written order to commence
CLAUSE 17-A: Defect liability clause
The Defects Liability period shall be 18 months from the certified date of completion which should include one monsoon."""

REAL_TITLES = [
    ("Resurfacing of Various Roads under Scsp / Mmgsy / Bk / 2026-27 / Package No. 13, Ta. Deesa, "
     "(1) Athamanovas to Umedpura Road, Km. 0/0 to 3/150", "recarpet", 0.0, 3.15, "Deesa"),
    ("Resurfacing of Various Roads under Scsp / Mmgsy / Bk / 2026-27 / Package No. 18, Ta. Deesa, "
     "(1) Ghada to Kotha Road, Km. 0/0 to 3/600", "recarpet", 0.0, 3.6, "Deesa"),
    ("Resurfacing of Various Roads under Owr / Mmgsy / Bk / 2026-27 / Package No. 25, Ta. Dhanera, "
     "(1) Charda to Goliya Approach Road, Km. 0/0 to 1/350", "recarpet", 0.0, 1.35, "Dhanera"),
]


def test_form_b1():
    f = extract_rules(REAL_B1)
    assert f["doc_type"] == "tender"
    assert f["estimated_cost"] == 26139631.52
    assert f["completion_period_days"] == 75
    assert f["liability_months"] == 18
    assert f["title"].startswith("Tender For Development of Parking")


def test_real_titles():
    for title, wt, k0, k1, taluka in REAL_TITLES:
        f = extract_rules(f"NOTICE INVITING TENDER\nName of Work : {title}")
        assert f["work_type"] == wt, title
        assert (f["start_km"], f["end_km"]) == (k0, k1), title
        assert f["taluka"] == taluka
        assert f["scheme"] and "Package" in f["scheme"]


def test_chainage_formats():
    assert parse_chainage("Km. 12/400 to 18/200") == (12.4, 18.2)
    assert parse_chainage("km 4.0 to 8.0") == (4.0, 8.0)
    assert parse_chainage("Ch. 3/050 - 5/000") == (3.05, 5.0)


if __name__ == "__main__":
    test_form_b1()
    test_real_titles()
    test_chainage_formats()
    print("all extraction tests passed")
