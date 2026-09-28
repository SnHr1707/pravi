"""Turn a tender / award / completion PDF into structured fields.

Always runs a rule-based reader tuned to Gujarat R&B formats (Form B-1, nprocure notices,
work orders, completion certificates). Optionally adds an LLM:
  - LLM_PROVIDER=openai_compatible  -> open-source models (Llama / Qwen / Mistral) via Ollama, vLLM, Groq…
  - LLM_PROVIDER=anthropic          -> Claude API
If the LLM is unavailable, the rule-based result is used, so the demo never breaks.
"""
import io
import json
import re
from datetime import date, datetime
from typing import Optional, Tuple

import httpx

from .config import ANTHROPIC_API_KEY, LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_PROVIDER

FIELDS = ["doc_type", "tender_id", "title", "road_code", "road_name", "start_km", "end_km", "asset_code",
          "work_type", "estimated_cost", "awarded_cost", "contractor", "completion_period_days",
          "liability_months", "tender_date", "award_date", "completion_date", "district", "taluka", "scheme",
          "sanction_no", "sanction_date"]

REQUIRED = {
    "tender": ["tender_id", "title", "work_type", "estimated_cost", "liability_months", "tender_date"],
    "award": ["tender_id", "contractor", "awarded_cost", "award_date", "completion_period_days"],
    "completion": ["tender_id", "contractor", "completion_date"],
    "sanction": ["title", "estimated_cost", "sanction_date"],
}


def pdf_text(data: bytes) -> str:
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        return "\n".join((p.extract_text() or "") for p in pdf.pages)


# ------------------------------------------------------------------ rules

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_date(s: str) -> Optional[str]:
    s = s.strip()
    m = re.search(r"(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{4})", s)
    if m:
        d, mo, y = map(int, m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?[\s\-]+([A-Za-z]{3,9})[,\s\-]+(\d{4})", s)
    if m and m.group(2)[:3].lower() in MONTHS:
        try:
            return date(int(m.group(3)), MONTHS[m.group(2)[:3].lower()], int(m.group(1))).isoformat()
        except ValueError:
            return None
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    return None


def parse_money(num: str, unit: Optional[str]) -> Optional[float]:
    try:
        v = float(num.replace(",", "").strip().rstrip("."))
    except ValueError:
        return None
    u = (unit or "").lower()
    if u.startswith("lakh") or u.startswith("lac"):
        v *= 1e5
    elif u.startswith("crore") or u.startswith("cr"):
        v *= 1e7
    return v


def _find(pattern, text, flags=re.I):
    m = re.search(pattern, text, flags)
    return m


def _date_after(labels, text) -> Optional[str]:
    for lab in labels:
        m = re.search(lab + r"[^\n:]*[:\-]?\s*([^\n]{6,40})", text, re.I)
        if m:
            d = parse_date(m.group(1))
            if d:
                return d
    return None


def work_type_from(text: str) -> Optional[str]:
    t = text.lower()
    rules = [
        (r"widen", "widening"),
        (r"re-?surfac|re-?carpet|overlay|renewal coat|carpet(?:ing)?\b", "recarpet"),
        (r"strengthen|rehabilit|rehab\b|reconstruct", "rehab"),
        (r"patch|pothole|special repair|repairs? (?:of|to)|maintenance of", "repair"),
        (r"waterproof", "waterproofing"),
        (r"structural repair|retrofit", "structural_repair"),
        (r"construction of|new road|providing (?:and|&) constructing|development of", "new_construction"),
    ]
    for pat, wt in rules:
        if re.search(pat, t):
            return wt
    return None


NUM_WORDS = r"(?:\s*\([A-Za-z \-]+\))?"      # "75 (Seventy Five) Days"
SEP = r"\s*[:\-–—]+\s*"                       # ":", ":-", "–"


def parse_chainage(text: str):
    """Gujarat R&B writes chainage as 'Km. 0/0 to 3/150' (km/metres); also accept 'km 4.0 to 8.0'."""
    m = re.search(r"(?:\bKm\.?|\bCh(?:ainage)?\.?)\s*(\d+)\s*/\s*(\d+)\s*(?:to|-|–)\s*(?:Km\.?\s*)?(\d+)\s*/\s*(\d+)",
                  text, re.I)
    if m:
        a = int(m.group(1)) + int(m.group(2)) / 1000
        b = int(m.group(3)) + int(m.group(4)) / 1000
        return round(min(a, b), 3), round(max(a, b), 3)
    m = re.search(r"(?:\bkm\.?|\bch(?:ainage)?\.?)\s*([0-9]+(?:\.[0-9]+)?)\s*(?:to|-|–)\s*(?:km\.?\s*)?([0-9]+(?:\.[0-9]+)?)",
                  text, re.I)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return min(a, b), max(a, b)
    return None, None


def _value_after(label: str, text: str) -> Optional[str]:
    """Text after 'Label :-' up to the end of the line, joined with wrapped continuation lines."""
    m = re.search(label + SEP + r"(.+)", text, re.I)
    if not m:
        return None
    val = m.group(1).strip()
    for nxt in text[m.end():].splitlines()[1:4]:
        if not nxt.strip() or re.match(r"^\s*(?:\(\d+\)\s*)?[A-Za-z][A-Za-z ()/&.\-]{2,45}\s*[:\-–—]", nxt):
            break
        val += " " + nxt.strip()
    return val.strip()


def extract_rules(text: str) -> dict:
    out = {k: None for k in FIELDS}
    up = text.upper()
    if "COMPLETION CERTIFICATE" in up or "CERTIFICATE OF COMPLETION" in up:
        out["doc_type"] = "completion"
    elif any(k in up for k in ("LETTER OF ACCEPTANCE", "AWARD OF CONTRACT", "WORK ORDER", "ACCEPTANCE OF TENDER")):
        out["doc_type"] = "award"
    elif any(k in up for k in ("NOTICE INVITING", "TENDER NOTICE", "E-TENDER", "FORM B-1", "FORM B-2",
                               "PERCENTAGE RATE TENDER", "ITEM RATE TENDER")) or re.search(r"\bNIT\b", up):
        out["doc_type"] = "tender"
    elif "ADMINISTRATIVE APPROVAL" in up or "TECHNICAL SANCTION" in up or "SANCTION ORDER" in up:
        out["doc_type"] = "sanction"

    m = _find(r"(?:Tender|NIT|Bid)\s*(?:ID|No\.?|Number|Ref(?:erence)?(?:\s*No\.?)?)" + SEP + r"([A-Za-z0-9][A-Za-z0-9/\-_. ]{3,50})", text)
    if m:
        out["tender_id"] = re.split(r"\s{2,}|\s+Dt\.?|\s+Date", m.group(1).strip())[0].strip(" .,")
    title = _value_after(r"Name of (?:the )?Work", text) or _value_after(r"\(1\)\s*Name of work", text)
    out["title"] = title
    m = _find(r"\b(SH|MDR|ODR|VR)\s?-\s?([A-Z]{1,4}\d{0,3}|\d{1,3})\b", text, 0)
    if m:
        out["road_code"] = f"{m.group(1)}-{m.group(2)}"
    rn = _value_after(r"Road(?:\s*Name)?", text)
    if rn:
        out["road_name"] = re.split(r"\s*\(", rn)[0].strip()
    elif title:
        m = re.search(r"([A-Z][A-Za-z]+(?:[\s\-–]+(?:to\s+)?[A-Z][A-Za-z]+){1,4}\s+(?:Approach\s+)?Road)", title)
        if m:
            out["road_name"] = m.group(1).strip()
    out["start_km"], out["end_km"] = parse_chainage(title or "") if title and parse_chainage(title)[0] is not None \
        else parse_chainage(text)
    m = _find(r"\b(VAD-(?:BR|CU|BL|RS)-\d{3})\b", text, 0)
    if m:
        out["asset_code"] = m.group(1)
    money = r"[^0-9\n]{0,40}?(?:Rs\.?|INR|₹)?\s*([0-9][0-9,]*(?:\.[0-9]+)?)\s*(lakhs?|lacs?|crores?|cr\b)?"
    m = _find(r"Estimated\s*(?:Cost|Value|Amount)" + money, text)
    if m:
        out["estimated_cost"] = parse_money(m.group(1), m.group(2))
    if out["estimated_cost"] is None:
        m = _find(r"Amount of (?:Administrative Approval|A\.?\s?A\.?|Technical Sanction|Sanction)" + money, text)
        if m:
            out["estimated_cost"] = parse_money(m.group(1), m.group(2))
    m = _find(r"(?:A\.\s?A\.|Administrative Approval|Sanction Order)\s*No\.?" + SEP + r"([A-Za-z0-9][A-Za-z0-9/\-_. ]{3,50})", text)
    if m:
        out["sanction_no"] = re.split(r"\s{2,}|\s+Dt\.?|\s+Date", m.group(1).strip())[0].strip(" .,")
    out["sanction_date"] = _date_after([r"Date of (?:Administrative Approval|A\.\s?A\.|Sanction)", r"Sanctioned on"], text)
    m = _find(r"(?:Contract|Accepted|Awarded|Agreement|Tendered)\s*(?:Value|Amount|Cost|Price)" + money, text)
    if m:
        out["awarded_cost"] = parse_money(m.group(1), m.group(2))
    c = _value_after(r"(?:Name of (?:the )?(?:Contractor|Agency)|Contractor|Agency|Awarded to)", text)
    if c:
        out["contractor"] = re.sub(r"\s{2,}.*$", "", c).strip().rstrip(",.")
    # Gujarat Form B-1 Clause 17-A: "The Defects Liability period shall be 18 months from the certified date of completion"
    m = _find(r"Defects?\s*Liability\s*Period[^0-9]{0,80}?([0-9]+)" + NUM_WORDS + r"\s*(months?|years?)", text)
    if m:
        n = int(m.group(1))
        out["liability_months"] = n * 12 if m.group(2).lower().startswith("year") else n
    m = _find(r"(?:Time\s*(?:limit|allowed for completion|of completion|for completion)?|Period\s*(?:of|for)\s*Completion)"
              + SEP + r"[^0-9\n]{0,20}([0-9]+)" + NUM_WORDS + r"\s*(days?|months?)", text)
    if not m:
        m = _find(r"(?:Time|Period)\s*(?:of|for|allowed for)\s*Completion[^0-9\n]*([0-9]+)" + NUM_WORDS + r"\s*(days?|months?)", text)
    if m:
        n = int(m.group(1))
        out["completion_period_days"] = n * 30 if m.group(2).lower().startswith("month") else n
    out["tender_date"] = _date_after([r"Date of (?:Publication|Issue|Tender)", r"Tender Date", r"Published on",
                                      r"Start Date", r"Bid (?:Start|Publish) Date"], text)
    out["award_date"] = _date_after([r"Date of (?:Award|Acceptance|Work Order)", r"Award Date", r"LoA Date",
                                     r"Work Order (?:No\.?.{0,40}?)?Dt"], text)
    out["completion_date"] = _date_after([r"Actual Date of Completion", r"Certified Date of Completion",
                                          r"Completed on", r"Work completed on", r"Date of Completion"], text)
    m = _find(r"(?:District|Dist\.)" + r"\s*[:\-–]*\s*([A-Z][A-Za-z]+)", text)
    if m:
        out["district"] = m.group(1).strip()
    else:
        m = _find(r"(?:R\s*&\s*B|Roads? (?:&|and) Buildings?)\s*(?:\(State\)\s*)?Division\s*[,:\-–]*\s*([A-Z][A-Za-z]+)", text)
        if m:
            out["district"] = m.group(1)
    m = _find(r"\bTa\.\s*([A-Z][A-Za-z]+)", text, 0)
    if m:
        out["taluka"] = m.group(1)
    m = _find(r"under\s+([A-Za-z /]+?)\s*/\s*(\d{4}-\d{2})\s*/\s*Package\s+No\.?\s*(\d+)", text)
    if m:
        out["scheme"] = f"{m.group(1).strip()} {m.group(2)}, Package {m.group(3)}"
    out["work_type"] = work_type_from(out["title"] or text)
    return out


# ------------------------------------------------------------------ LLM

PROMPT = """You extract structured data from Gujarat Roads & Buildings (R&B) department documents:
tender notices / Form B-1 or B-2 percentage-rate tenders, letters of acceptance / work orders, and
completion certificates. They may be in English, Gujarati or both.
Notes on Gujarat conventions:
- Chainage is written "Km. 12/400 to 18/200" meaning km 12.400 to 18.200 -> start_km 12.4, end_km 18.2
- Defect liability is in Clause 17-A ("Defects Liability period shall be 18 months from the certified date of completion")
- "Ta." = taluka, "Dist." = district; schemes like MMGSY, SCSP, OWR, PMGSY with "Package No."
- Amounts may be written in Indian grouping (Rs. 2,61,39,631.52) or in lakh/crore

Return ONLY a JSON object with exactly these keys (use null when absent, never guess):
doc_type: "sanction" (administrative approval / technical sanction) | "tender" | "award" | "completion" | "other"
tender_id: string
title: name of work
road_code: like "SH-VP" or "MDR-KS" if a road code appears, else null
road_name: string
start_km, end_km: numbers (chainage in km)
asset_code: like "VAD-BR-001" if present
work_type: one of new_construction, widening, recarpet, repair, rehab, waterproofing, structural_repair
estimated_cost, awarded_cost: numbers in rupees (convert lakh/crore)
contractor: string
completion_period_days: integer
liability_months: integer (defect liability period)
tender_date, award_date, completion_date, sanction_date: "YYYY-MM-DD"
sanction_no: administrative approval / sanction order number
district: string
taluka: string
scheme: scheme and package if mentioned, e.g. "Scsp / Mmgsy / Bk 2026-27, Package 13"
field_confidence: object mapping each non-null key to a 0-1 confidence

Document text:
<<<
{text}
>>>"""


def _parse_json(content: str) -> Optional[dict]:
    m = re.search(r"\{.*\}", content or "", re.S)
    if not m:
        return None
    data = json.loads(m.group(0))
    return {k: data.get(k) for k in FIELDS} | {"field_confidence": data.get("field_confidence") or {}}


def _openai_compatible(text: str) -> Optional[dict]:
    """Open-source models (Llama, Qwen, Mistral…) served by Ollama, vLLM, Groq, Together, OpenRouter, etc."""
    headers = {"content-type": "application/json"}
    if LLM_API_KEY:
        headers["authorization"] = f"Bearer {LLM_API_KEY}"
    if "openrouter.ai" in LLM_BASE_URL:
        headers["HTTP-Referer"] = "https://github.com/pravi-rnb"
        headers["X-Title"] = "Pravi R&B Asset Tracker"
    r = httpx.post(f"{LLM_BASE_URL.rstrip('/')}/chat/completions", headers=headers, timeout=90, json={
        "model": LLM_MODEL, "temperature": 0,
        "messages": [{"role": "system", "content": "You return only valid JSON."},
                     {"role": "user", "content": PROMPT.format(text=text[:12000])}],
    })
    r.raise_for_status()
    return _parse_json(r.json()["choices"][0]["message"]["content"])


def _anthropic(text: str) -> Optional[dict]:
    r = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
        json={"model": LLM_MODEL, "max_tokens": 1500,
              "messages": [{"role": "user", "content": PROMPT.format(text=text[:15000])}]},
        timeout=60,
    )
    r.raise_for_status()
    return _parse_json("".join(b.get("text", "") for b in r.json().get("content", [])))


LAST_LLM_ERROR = {"error": None}


def extract_llm(text: str) -> Optional[dict]:
    if LLM_PROVIDER == "none":
        return None
    try:
        out = None
        if LLM_PROVIDER == "openai_compatible":
            out = _openai_compatible(text)
        elif LLM_PROVIDER == "anthropic":
            out = _anthropic(text)
        LAST_LLM_ERROR["error"] = None if out else "Model returned no JSON"
        return out
    except httpx.HTTPStatusError as e:
        LAST_LLM_ERROR["error"] = f"HTTP {e.response.status_code}: {e.response.text[:300]}"
    except Exception as e:  # network / API / parse errors fall back to rules
        LAST_LLM_ERROR["error"] = f"{type(e).__name__}: {e}"[:300]
    print(f"[extraction] LLM ({LLM_PROVIDER}) failed, using rules: {LAST_LLM_ERROR['error']}")
    return None


def score(fields: dict) -> float:
    need = REQUIRED.get(fields.get("doc_type") or "", ["tender_id", "title"])
    found = sum(1 for k in need if fields.get(k) not in (None, ""))
    return round(found / len(need), 2)


def extract(text: str) -> Tuple[dict, str, float]:
    """Returns (fields, method, confidence)."""
    llm = extract_llm(text)
    rules = extract_rules(text)
    if llm:
        # rules fill any gaps the model left
        merged = {k: (llm.get(k) if llm.get(k) not in (None, "") else rules.get(k)) for k in FIELDS}
        return merged, "llm", score(merged)
    return rules, "rules", score(rules)


def coerce(fields: dict) -> dict:
    """Clean user-edited fields coming back from the review screen."""
    out = {}
    for k in FIELDS:
        v = fields.get(k)
        if v in ("", None):
            out[k] = None
        elif k in ("start_km", "end_km", "estimated_cost", "awarded_cost"):
            try:
                out[k] = float(str(v).replace(",", ""))
            except ValueError:
                out[k] = None
        elif k in ("completion_period_days", "liability_months"):
            try:
                out[k] = int(float(v))
            except ValueError:
                out[k] = None
        elif k.endswith("_date"):
            out[k] = parse_date(str(v)) or None
        else:
            out[k] = str(v).strip()
    return out


def to_date(s: Optional[str]) -> Optional[date]:
    if not s:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None
