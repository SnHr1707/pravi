"""Generate the synthetic sample PDFs used in the demo (python scripts/make_sample_docs.py).

They are modelled on the layout of public tender notices, letters of acceptance and
completion certificates, but every value in them is fictional demo data.
"""
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

OUT = Path(__file__).resolve().parent.parent / "sample_docs"
OUT.mkdir(exist_ok=True)
T = date.today()


def fmt(d):
    return d.strftime("%d/%m/%Y")


def make(name, title, rows, paras):
    c = canvas.Canvas(str(OUT / name), pagesize=A4)
    w, h = A4
    y = h - 22 * mm
    c.setFont("Helvetica", 8)
    c.setFillColorRGB(0.7, 0.1, 0.1)
    c.drawCentredString(w / 2, y + 8 * mm, "SAMPLE - SYNTHETIC DOCUMENT FOR DEMO (all values fictional)")
    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(w / 2, y, "ROADS & BUILDINGS DIVISION, VADODARA")
    y -= 6 * mm
    c.setFont("Helvetica", 10)
    c.drawCentredString(w / 2, y, "District: Vadodara")
    y -= 12 * mm
    c.setFont("Helvetica-Bold", 14)
    c.drawCentredString(w / 2, y, title)
    y -= 12 * mm
    for label, value in rows:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(20 * mm, y, f"{label}:")
        c.setFont("Helvetica", 10)
        lines = []
        cur = ""
        for word in str(value).split():
            if len(cur) + len(word) > 70:
                lines.append(cur)
                cur = word
            else:
                cur = (cur + " " + word).strip()
        lines.append(cur)
        for ln in lines:
            c.drawString(80 * mm, y, ln)
            y -= 6 * mm
        y -= 1 * mm
    y -= 4 * mm
    c.setFont("Helvetica", 10)
    for p in paras:
        cur = ""
        for word in p.split():
            if len(cur) + len(word) > 95:
                c.drawString(20 * mm, y, cur)
                y -= 5.5 * mm
                cur = word
            else:
                cur = (cur + " " + word).strip()
        c.drawString(20 * mm, y, cur)
        y -= 9 * mm
    c.drawString(130 * mm, 40 * mm, "Executive Engineer")
    c.drawString(130 * mm, 35 * mm, "R&B Division, Vadodara")
    c.save()


# Layout follows Gujarat R&B practice: Form B-1 percentage-rate tender with a "Memorandum of works in brief",
# chainage as "Km. 4/0 to 8/0", Clause 17-A defect liability, nprocure-style numeric tender IDs.

# 1. A paid repair tender on a stretch still under the original contractor's liability -> red flag
make("1_tender_Vadodara-Waghodia_special_repair.pdf", "FORM B-1  PERCENTAGE RATE TENDER AND CONTRACT FOR WORKS", [
    ("Tender ID", "781456"),
    ("Date of Publication", fmt(T)),
    ("Name of work", "Special repair (patch work) to Vadodara Waghodia Road, Km. 4/0 to 8/0, Ta. Waghodia, Dist. Vadodara"),
    ("Division", "R&B Division, Vadodara"),
    ("(2) Estimated Cost", "Rs. 12,40,318.00"),
    ("(3) Earnest Money", "Rs. 12,404.00"),
    ("(5) Security Deposit", "5% of contract value"),
    ("(6) Time allowed for completion", "60 (Sixty) Days from the date of written order to commence"),
    ("Last date of online submission", fmt(T + timedelta(days=15))),
], ["CLAUSE 17-A: Defect liability clause. The contractor shall be responsible to make good and remedy at his own "
    "expense any defect which may develop or may be noticed before the period mentioned hereunder from the certified "
    "date of completion, within 15 days of receipt of the notice. The Defects Liability period shall be 6 months from "
    "the certified date of completion.",
    "Tender documents are available on the e-procurement portal. The Department reserves the right to reject any or all tenders."])

# 2. The work order (award) for the same tender
make("2_work_order_Vadodara-Waghodia_special_repair.pdf", "WORK ORDER / LETTER OF ACCEPTANCE", [
    ("Tender ID", "781456"),
    ("Date of Work Order", fmt(T)),
    ("Name of work", "Special repair (patch work) to Vadodara Waghodia Road, Km. 4/0 to 8/0, Ta. Waghodia, Dist. Vadodara"),
    ("Name of Agency", "Neel Buildcon"),
    ("Accepted Contract Value", "Rs. 11,85,210.00 (4.44% below estimated cost)"),
    ("Time Limit", "60 (Sixty) Days"),
], ["Your tender for the above work is accepted. You are directed to execute the agreement in Form B-1, furnish the "
    "security deposit and commence the work within 10 days."])

# 3. Completion certificate for the delayed widening work -> starts its liability clock
make("3_completion_Vadodara-Savli_widening.pdf", "COMPLETION CERTIFICATE", [
    ("Tender ID", "RNB/VAD/2025/0150"),
    ("Name of work", "Widening and strengthening of Vadodara Savli Road Km. 15/0 to 29/0 from 7.0 m to 10.0 m, Ta. Savli"),
    ("Name of Agency", "Saptarshi Constructions"),
    ("Contract Value", "Rs. 6,45,00,000.00"),
    ("Actual Date of Completion", fmt(T - timedelta(days=2))),
    ("Stipulated Date of Completion", fmt(T - timedelta(days=90))),
    ("Defects Liability Period", "36 (Thirty Six) months from the certified date of completion (Clause 17-A)"),
], ["Certified that the above work has been completed in all respects as per the contract and specifications.",
    "The Defects Liability period commences from the certified date of completion stated above."])

# 4. A legitimate resurfacing tender on an old road (out of liability) -> no flag
make("4_tender_Padra-Karjan_resurfacing.pdf", "NOTICE INVITING E-TENDER", [
    ("Tender ID", "781502"),
    ("Date of Publication", fmt(T)),
    ("Name of work", "Resurfacing of Various Roads under OWR / MMGSY / VD / 2026-27 / Package No. 07, Ta. Padra, "
                     "(1) Padra to Karjan Road, Km. 10/0 to 21/0"),
    ("Estimated Cost", "Rs. 66,02,418.40"),
    ("Time Limit", "4 (Four) Months including monsoon"),
    ("Defects Liability Period", "3 (Three) years from the certified date of completion"),
], ["Online tenders are invited from contractors registered with the Government of Gujarat in the appropriate class."])

# ---------------------------------------------------------------------------------------------
# N-series: the complete life of a brand-new road, Waghodia to Jarod (not in the inventory yet).
# Upload N1 → N4 in order, then report a pothole on it as a citizen, then upload N5.
ROAD = "Waghodia to Jarod Road"
WORK = "Construction of new 2-lane road from Waghodia to Jarod, Km. 0/0 to 12/0, Ta. Waghodia, Dist. Vadodara"
make("N1_approval_Waghodia-Jarod_new_road.pdf", "ADMINISTRATIVE APPROVAL AND TECHNICAL SANCTION", [
    ("A.A. No.", "RB/VAD/AA/2025/118"),
    ("Date of Administrative Approval", fmt(T - timedelta(days=400))),
    ("Name of work", WORK),
    ("Road", ROAD),
    ("Amount of Administrative Approval", "Rs. 18,40,00,000.00"),
    ("Estimated Cost", "Rs. 18,40,00,000.00"),
    ("Scheme", "Mukhyamantri Gram Sadak Yojana (MMGSY) 2025-26"),
], ["Administrative approval and technical sanction are hereby accorded for the above work.",
    "The Executive Engineer, R&B Division, Vadodara is directed to invite tenders on the e-procurement portal."])

make("N2_tender_Waghodia-Jarod_new_road.pdf", "FORM B-1  PERCENTAGE RATE TENDER AND CONTRACT FOR WORKS", [
    ("Tender ID", "781940"),
    ("Date of Publication", fmt(T - timedelta(days=370))),
    ("Name of work", WORK),
    ("Road", ROAD),
    ("Division", "R&B Division, Vadodara"),
    ("(2) Estimated Cost", "Rs. 18,40,00,000.00"),
    ("(3) Earnest Money", "Rs. 18,40,000.00"),
    ("(6) Time allowed for completion", "12 (Twelve) Months from the date of written order to commence"),
], ["CLAUSE 17-A: Defect liability clause. The contractor shall be responsible to make good and remedy at his own "
    "expense any defect which may develop or may be noticed before the period mentioned hereunder from the certified "
    "date of completion, within 15 days of receipt of the notice. The Defects Liability period shall be 36 months from "
    "the certified date of completion which should include one monsoon."])

make("N3_work_order_Waghodia-Jarod_new_road.pdf", "WORK ORDER / LETTER OF ACCEPTANCE", [
    ("Tender ID", "781940"),
    ("Date of Work Order", fmt(T - timedelta(days=340))),
    ("Name of work", WORK),
    ("Road", ROAD),
    ("Name of Agency", "Shreeji Infrastructure"),
    ("Accepted Contract Value", "Rs. 17,62,40,000.00 (4.22% below estimated cost)"),
    ("Time Limit", "12 (Twelve) Months"),
], ["Your tender for the above work is accepted. You are directed to execute the agreement in Form B-1, furnish the "
    "security deposit and commence the work within 10 days."])

make("N4_completion_Waghodia-Jarod_new_road.pdf", "COMPLETION CERTIFICATE", [
    ("Tender ID", "781940"),
    ("Name of work", WORK),
    ("Road", ROAD),
    ("Name of Agency", "Shreeji Infrastructure"),
    ("Contract Value", "Rs. 17,62,40,000.00"),
    ("Actual Date of Completion", fmt(T - timedelta(days=45))),
    ("Defects Liability Period", "36 (Thirty Six) months from the certified date of completion (Clause 17-A)"),
], ["Certified that the above work has been completed in all respects as per the contract and specifications.",
    "The Defects Liability period commences from the certified date of completion stated above."])

make("N5_tender_Waghodia-Jarod_special_repair.pdf", "FORM B-1  PERCENTAGE RATE TENDER AND CONTRACT FOR WORKS", [
    ("Tender ID", "782311"),
    ("Date of Publication", fmt(T - timedelta(days=3))),
    ("Name of work", "Special repair (patch work) to Waghodia to Jarod Road, Km. 5/0 to 7/0, Ta. Waghodia, Dist. Vadodara"),
    ("Road", ROAD),
    ("(2) Estimated Cost", "Rs. 8,75,000.00"),
    ("(6) Time allowed for completion", "30 (Thirty) Days"),
], ["CLAUSE 17-A: The Defects Liability period shall be 6 months from the certified date of completion."])

for old in ["1_tender_MDR-VW_patch_repair.pdf", "2_award_MDR-VW_patch_repair.pdf", "3_completion_SH-VS_widening.pdf",
            "4_tender_ODR-PK_recarpet.pdf"]:
    (OUT / old).unlink(missing_ok=True)
print("wrote", sorted(p.name for p in OUT.glob("*.pdf")))
