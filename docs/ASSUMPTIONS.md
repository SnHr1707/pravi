# Pravi — Assumptions

## Scope
1. **Department and place:** the prototype is built for the **Roads & Buildings (R&B) Department, Government of Gujarat**. The demo district is **Vadodara**, and each login belongs to one district.
2. **Assets covered:** road sections (SH, MDR, ODR, village roads), bridges, culverts/drains and government buildings. Roads are covered in depth; the others are lighter. Road-safety furniture (signs, crash barriers) and non-infrastructure items (vehicles, IT, furniture) are out of scope.
3. **Road sections:** a road is tracked as sections identified by **road + km range**. Works, complaints and liability are matched by km range, not by road name.

## Contracts and documents
4. Contract terms follow Gujarat R&B practice: **Form B-1** (percentage-rate tender), with the **Defects Liability Period in Clause 17-A**, counted **from the certified date of completion**.
5. **Defect notices:** a defect reported during that period must be fixed by the contractor **at their own cost within 15 days of the notice**.
6. **Chainage** is written as "Km. 4/0 to 8/0" (km/metres) and read as km 4.000–8.000.
7. **Tender IDs** are unique. Later documents for the same work (work order, completion certificate) are linked by Tender ID.
8. A **tender** for an asset that has an **approved work without a tender** continues that work, rather than creating a new one.
9. **Missing completion date:** it is estimated as **work-order date + time limit** and marked "estimated". A missing start date is assumed to be **10 days after the work order**.
10. **Text PDFs only:** documents must contain a text layer. Scanned PDFs need OCR, which is on the roadmap. Gujarati-only documents are read best with the optional LLM.
11. **Engineer review:** extraction can be wrong, so an engineer checks every field before anything is saved.

## Data
12. **Real formats, fictional data:** the document formats and wording come from real, public Gujarat R&B documents. All demo data is fictional: road codes (SH-VP etc.), contractors, amounts, complaints, inspections and sample PDFs.
13. **Public vs internal documents:** tender notices and award notices are public. Approval orders, completion certificates, bills, inspections and complaints are internal, so they are **simulated**. In production, Pravi runs **inside the department** with official access to them.
14. **Road geometry is approximate.** Demo roads are hand-traced between real towns. Roads created from documents are drawn as a straight line between the two places named ("A to B Road"), found with OpenStreetMap place search. The real R&B GIS network would replace both.
15. **Relative dates:** demo dates are set relative to today, so the planted cases (liability ending, overdue inspections) stay valid on any day.

## Rules and thresholds (all configurable)
16. **Repeat failure:** 3 or more repairs on the same asset within 12 months.
17. **Ageing road:** no major renewal (re-carpeting, rehabilitation or reconstruction) in 7 years.
18. **Bridge inspections:** due every 6 months (before and after the monsoon). Overdue by more than 12 months, or rated 1/5, counts as **urgent**.
19. **Culverts:** must be cleaned before the monsoon, between **1 March and 15 June**.
20. **Buildings over 15 years old:** need a structural audit every 5 years.
21. **Stale complaint:** verified but not fixed within 7 days. A **contractor notice is ignored** after 14 days.
22. **Liability expiring:** flagged 60 days before the end, to inspect while repairs are still free.
23. **Complaint handling:** a report is linked to the nearest road section within 2 km. Reports of the same problem within 300 m are merged. At most 20 reports per device per hour.

## Hierarchy and deadlines
24a. **Chain of command:** Secretary → Chief Engineer (wing) → Superintending Engineer (circle) → Executive Engineer (division) → Deputy Executive Engineer (sub-division) → Additional Assistant Engineer (section), as on the public R&B organisation chart. Only the **State R&B wing**, **Vadodara Circle** and **Vadodara Division** are onboarded; other circles and divisions appear as "not on Pravi yet". Section officers (AAE) work under the sub-division login for now.
24b. **Sub-divisions** in the demo: Vadodara (Vadodara, Waghodia, Savli, Desar talukas), Padra (Padra, Karjan, Sinor) and Dabhoi (Dabhoi). An asset belongs to the sub-division of its taluka.
24c. **Sanction limits are illustrative:** Deputy EE up to ₹5 lakh, EE up to ₹50 lakh, SE up to ₹2 crore, CE above. The real limits come from the state's delegation of financial powers.
24d. **Repair deadlines:** potholes and waterlogging 48 hours (24 hours from 15 June to 30 September), broken railings 24 hours, other issues 7 days — based on Mumbai's 24-hour monsoon rule and the Bombay High Court's 48-hour limit. Late → EE, 3× late → SE, 7× late → CE.
24e. **Road digging (from Mumbai's trenching policy):** no digging in the first 12 months of a road's guarantee except emergencies; no digging 1 June – 30 September except emergencies; the utility pays a restoration charge (illustrative ₹1,500–3,200 per metre by road category) and is responsible for defects at the dug spot for 12 months after restoration.
24f. **Structural classes** C1 (dangerous), C2A (major repair, vacate), C2B (major repair, stay), C3 (minor) follow the Mumbai classification and are entered from the audit report.
24g. **Traffic** (PCU/day) for demo roads is illustrative; roads created from documents default to 1,000 PCU/day. In production it comes from R&B's traffic census.

## Priority and budget
24. **Priority score:**
    `100 × (0.30 condition + 0.25 criticality + 0.20 complaints + 0.15 age + 0.10 repeat repairs)`.
    The Executive Engineer can change the weights. Liability changes **who pays**, not how urgent something is.
25. **Criticality:** SH 1.0, MDR 0.7, ODR 0.5, village road 0.3. Bridges and hospitals ×1.2 (capped at 1).
26. **Budget planner unit rates are illustrative:**
    - Resurfacing per km: SH ₹14 lakh, MDR ₹10 lakh, ODR ₹6 lakh, VR ₹4 lakh.
    - Reconstruction costs **3×** resurfacing.
    - A road at condition 2–3 has a **50% chance of failing** if deferred.
    - Early-action bonus is 1.5×.
    - Bridge rehabilitation is ₹1.2 crore.
27. **Rural reserve:** by default **25% of the budget** is reserved for village and ODR roads. This is adjustable.
28. **Flags are leads, not proof:** every flag is for human review, not evidence of wrongdoing.

## Technology
29. **Document reading:** the rule-based reader always runs. The **open-source LLM (Qwen via OpenRouter)** is optional and is used when a key is set. In production, an open model on a state data-centre server keeps documents in India.
30. **Logins:** demo accounts (Executive Engineer, Deputy Engineer, Auditor) stand in for **government SSO**.
31. **Languages:** the citizen app is in **English, Gujarati and Hindi**. Staff screens are in English for now.
32. **Hosting:** free tiers (Vercel + Neon). The first request after a period without use can take a few seconds while the server starts.
33. **Uploads:** up to about 4.5 MB per upload on Vercel. Photos are compressed on the phone first.
