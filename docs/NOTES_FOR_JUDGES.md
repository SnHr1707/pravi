# Pravi — Notes for the judges

**Pravi keeps one lifelong record for every road, bridge, culvert and government building of Gujarat's R&B department.** It builds that record from the documents R&B already produces (approval orders, tenders, work orders, completion certificates) and tells officers three things:

- **Who must pay for a repair.** If the contractor is still under the defect-liability guarantee, they must repair it for free.
- **What to fix first.**
- **Where each rupee does the most good.**

## Links and logins
- **Live app:** `<add your production Vercel URL>` (Staff login and the citizen app `/report` are both on it)
- **Code:** `<add your GitHub URL>` · API docs at `/docs`

| Role | Username | Password | Can do |
|---|---|---|---|
| Chief Engineer (State wing) | `ce_state` | `Chief@123` | Whole wing; works above ₹2 crore; 7×-late complaints |
| Superintending Engineer (Vadodara Circle) | `se_vadodara` | `Super@123` | All divisions; works up to ₹2 crore |
| Executive Engineer (Vadodara Division) | `ee_vadodara` | `Exec@123` | Division; works up to ₹50 lakh, digging permits, budget plan, settings, reset demo |
| Deputy Executive Engineer (sub-divisions) | `de_vadodara`, `de_padra`, `de_dabhoi` | `Engineer@123` | Own talukas: complaints, inspections, documents, works up to ₹5 lakh |
| Auditor | `auditor_vadodara` | `Audit@123` | View only |
| Citizen | no login | | Report a problem, track the ticket |

## The problem we chose, and why
We asked what "infrastructure asset inventory" meant here. The answer was **R&B, Gujarat**, tracking **every** asset rather than only those needing maintenance. So we focused on the three things that matter most for R&B assets.

**1. Where the money goes.** R&B spends mostly through works contracts, and every contract carries a Defects Liability Period (Form B-1, Clause 17-A). Nobody tracks those guarantee windows, so departments can pay for repairs a contractor owes for free.

**2. Where lives are at risk.** Bridges and hospital buildings fail rarely but catastrophically, so their inspections must not be missed.

**3. What citizens feel.** Potholes and waterlogging are what people complain about, and complaints often get closed without a real fix.

## What is different about Pravi
1. **The inventory builds itself from paperwork.** Upload a PDF and Pravi reads the name of work, road, chainage ("Km. 4/0 to 8/0"), taluka, cost, contractor and guarantee period. It then creates or updates the asset's lifecycle. **No survey, no data entry.** It was tested against wording from real Gujarat R&B documents.
2. **Guarantee (defect liability) tracking by km.** For any spot on any road, on any date, Pravi knows if a contractor must fix it for free. It flags a paid repair on a stretch still under guarantee **before the money is spent**, and generates the 15-day repair notice.
3. **A citizen loop that can't be faked.** Citizens report in English, Gujarati or Hindi with no login. Reports snap to the right road and km, and duplicates merge. **A repair only closes when the citizen confirms it**; "not fixed" reopens it and sends it back.
4. **Priority you can explain.** A 0–100 score from condition, importance, complaints, age and repeat repairs, with weights the department controls. Twelve alerts cover things like overdue bridge inspections, a culvert not cleaned before the monsoon, contractors ignoring notices, delayed works, unsafe (C1/C2A) structures and roads dug by utilities but not restored.
5. **A budget planner that is fair to villages.** Free fixes come first, safety second, then the most people helped per rupee. **A share of the budget is reserved for village roads**, so low-traffic villages aren't always last.
6. **Open-source AI, optional.** Qwen via OpenRouter (or Ollama/vLLM on a state server) reads messy PDFs. A rule-based reader always runs underneath, so it works with no AI and no internet dependency.

7. **Built around R&B's chain of command.** Chief Engineer → Superintending Engineer → Executive Engineer → Deputy Executive Engineer. Each login sees its own office and everything below it; senior officers get a league table of the units under them. Works go to the officer whose sanction limit covers the cost, and late complaints escalate up the chain by themselves.
8. **Ideas from Mumbai (BMC).** A 24–48 hour repair deadline on every complaint; road-digging permits for utilities (no digging in a road's first guarantee year or in the monsoon, and the utility pays for damage where it dug); photo proof for repairs and drain cleaning; C1–C3 structural safety classes; and a public performance scorecard per sub-division (`/performance`).

### Why drainage sits next to roads, bridges and buildings
Water is the main cause of road failure: a blocked culvert sends water into the road layers and potholes follow. Culverts and roadside drains are part of the road asset, R&B builds and cleans them, and pre-monsoon cleaning is one of its main yearly jobs. Tracking them together lets Pravi connect a waterlogging complaint to the culvert that was not cleaned. Bridges are river-crossing structures on the same roads; buildings are R&B's other half ("Roads **and Buildings**").

## How to see it in 5 minutes
1. **Home:** the to-do list, the map coloured by urgency and the alerts.
2. **Upload documents:** use the sample documents **N1 → N4** in order. A **new road (Waghodia to Jarod)** is created from its approval order, then goes through Tender out, Contract given and Completed, and gets a 36-month guarantee.
3. **Citizen app `/report`:** tap the new road and report a pothole. The reply says the contractor must repair it free.
4. **Complaints:** Check on site → Assign repair (a repair notice is generated) → Mark as repaired. The citizen confirms on `/track`.
5. **Upload N5:** a paid repair tender on that same road raises a red alert and appears as "Do not pay" in the **Budget plan**.

6. **Offices:** log in as `ce_state`, open **Offices**, and click down to a sub-division. Check **Complaints → Past deadline** and **Road digging**.

The full script is in `DEMO_GUIDE.md` (Part C covers the hierarchy and Mumbai features).

## Built for Bharat, built to scale
- **Nothing to install:** citizens use a web page that works on basic phones. Photos are compressed on the phone for slow networks, and the interface is available in three languages.
- **Scales district by district:** every record carries its district, so data can be partitioned by district and state. The serverless backend and managed Postgres scale up without re-architecture.
- **API-first:** everything is a REST API (`/docs`). Other departments, apps or a statewide dashboard can plug in, the way banks plug into UPI.
- **Uses what already exists:** contract PDFs, nprocure tender notices and OpenStreetMap. No new hardware or survey is needed to start.
- **Data can stay in India:** the LLM is optional and swappable for an open model hosted on a state server.

## Security and trust
- Passwords are hashed with bcrypt. Logins use JWT in an httpOnly cookie. Permissions depend on the role, and staff only see their own office and the offices below it.
- **History is append-only:** every action is recorded with who and when, and nothing is edited in place.
- Citizen reports are rate-limited, and a phone number is optional.
- Imports from URLs block internal network addresses.
- Every extracted field is reviewed by an engineer before it's saved.

## What is real and what is simulated
- **Real:** the Gujarat R&B document formats and wording (Form B-1, Clause 17-A, chainage notation, scheme and package titles). Real PDFs can be uploaded or imported from a URL.
- **Simulated (fictional):** demo roads, contractors, amounts, complaints and inspections. Internal documents (approvals, completion certificates) are simulated because they aren't public.
- **Approximate:** road lines on the map. R&B's GIS data would replace them.

## Known limitations
- Scanned PDFs need OCR, which isn't built yet.
- Roads created from documents are drawn as straight lines between the two named places.
- Staff screens are English only.
- Demo logins stand in for government SSO.
- The free hosting tier may take a few seconds to wake after being idle.

## Roadmap
- OCR for scanned and Gujarati-only documents.
- Integration with nprocure (tenders), IFMS (payments) and government SSO.
- Import of the R&B GIS road network.
- An offline field app, plus WhatsApp and voice complaint intake.
- Weights learned from real failure data, and predictive maintenance.

## Tech stack
React + TypeScript (Vite, React Router, TanStack Query, Tailwind, React-Leaflet) · FastAPI (Python) with SQLModel/SQLAlchemy · PostgreSQL (Neon) · JWT + bcrypt · pdfplumber + open-source LLM (Qwen via OpenRouter) · Vercel. A Docker image is also provided for running on a state data centre.
