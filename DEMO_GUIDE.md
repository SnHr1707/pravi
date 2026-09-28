# Pravi — setup and demo guide

This guide covers two things:
- **Part A:** set up the database (local or cloud).
- **Part B:** show the complete life of a brand-new road, driven entirely by PDFs from `sample_docs/`.

---

## Part A — Database setup

Pravi creates all its tables by itself on first start. You never write SQL.

### Option 1: Local SQLite (easiest, for testing on your laptop)
1. Do nothing. Without a `DATABASE_URL` setting, Pravi creates a file called `pravi.db` in the project folder.
2. Run `run.bat` (Windows) or `./run.sh` (Mac/Linux) and open http://localhost:8000.
3. **To start fresh at any time:** stop the server (`Ctrl + C`), delete `pravi.db`, and start again. Or use **Settings → Reset demo data** while it runs.

### Option 2: PostgreSQL on Neon (for the deployed site, where data must survive restarts)
1. Go to **https://neon.tech** and sign up (free, no card needed).
2. Click **New project**, name it `pravi`, and choose region **AWS Asia Pacific (Mumbai / Singapore)**.
3. On the project dashboard, click **Connect** and copy the **connection string**. It looks like:
   `postgresql://neondb_owner:xxxx@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
4. **Locally:** open `.env` in the project folder and add
   `DATABASE_URL=postgresql://neondb_owner:xxxx@ep-xxxx...neon.tech/neondb?sslmode=require`
   **On Render:** paste the same string into the service's **Environment → DATABASE_URL**.
5. Restart the server. On first start it creates the tables and loads the demo data. The terminal shows `seeded demo data`.
6. **Check it worked:** in Neon, open **Tables** (or the SQL editor and run `select count(*) from asset;`). You should see 28 demo assets.
7. **To wipe it:** use **Settings → Reset demo data** (Executive Engineer login), or drop the tables in Neon's SQL editor and restart.

### Optional: start with an EMPTY inventory
To build everything from your own PDFs, with no demo roads, add to `.env` (or to Render's environment):
```
SEED_DEMO=false
```
Then delete `pravi.db` (or reset). Only the three login accounts are created.

### All settings (`.env`)
| Setting | What it does | Example |
|---|---|---|
| `DATABASE_URL` | Where data is stored; empty means local `pravi.db` | Neon connection string |
| `JWT_SECRET` | Signs login sessions; any long random text | `k3Jd9…` |
| `OPENROUTER_API_KEY` | Turns on Qwen for reading PDFs (optional) | `sk-or-v1-…` |
| `LLM_MODEL` | Which model to use (optional) | `qwen/qwen3.6-27b` |
| `SEED_DEMO` | `false` means an empty start | `false` |

> `.env` is never committed or zipped. Keep real keys only there, **not** in `.env.example`.

---

## Part B — The full life of a new road, from PDFs

We'll build a road that does not exist in the system yet: **Waghodia to Jarod Road, km 0–12** (Ta. Waghodia, Dist. Vadodara). The PDFs are in `sample_docs/`, named `N1_…` to `N5_…`. They follow the real Gujarat R&B formats: administrative approval, Form B-1 tender with Clause 17-A, work order, and completion certificate. All names and amounts are fictional.

**Before you start:** log in as **Executive Engineer** (`ee_vadodara` / `Exec@123`) and keep two browser tabs open: the staff app and the citizen app (`/report`).

| Step | What you do | What happens | What to say to the judges |
|---|---|---|---|
| **1. Approval** | **Upload documents** → Try **N1** (or upload `N1_approval_…pdf`). The "Which road or building" box shows **+ Create new asset from this document**. Press **Save**. | A new road **Waghodia to Jarod Road km 0–12** is added to the inventory and drawn on the map. A work is created at **Approved** (₹18.40 cr). | "The department never typed this road in. It came from the approval order." |
| **2. Tender** | Try **N2** → **Save**. | The same work moves to **Tender out**. Pravi reads Tender ID 781940 and the 36-month guarantee from Clause 17-A. | "Pravi recognised the road by name and continued the approved work." |
| **3. Work order** | Try **N3** → **Save**. | The work moves to **Contract given**: Shreeji Infrastructure, ₹17.62 cr, 12 months. | "Every step is matched by Tender ID, with no manual linking." |
| **4. Completion** | Try **N4** → **Save**. | **Completed.** The 36-month guarantee starts, and the road shows **Under guarantee — contractor pays** until about 3 years from completion. | "From today, any defect on this road is the contractor's cost, and Pravi remembers that for 3 years." |
| **5. Look at it** | **Roads & buildings** → *Waghodia to Jarod Road*, open the **History** tab. | One timeline: registered → approved → tender → contract → work started → completed. | "One lifelong record per asset." |
| **6. Citizen complaint** | In the citizen tab (`/report`), tap **on the new road line** (between Waghodia and Jarod), choose **Pothole**, and submit. | The ticket says **"This road is still under guarantee. Shreeji Infrastructure must repair it at no cost to the public."** | "The citizen knows who is responsible, instantly." |
| **7. Engineer acts** | Staff tab → **Complaints** → the new ticket → **Check on site** → **Assign repair** (to the contractor, ₹0). | A **repair notice** PDF opens (Clause 17-A, 15 days). | "The notice is generated with the contract details filled in." |
| **8. Repair and confirm** | **Mark as repaired** (add any photo as the "after" photo — it is required; on a phone, also tap **Add my current location**), then in the citizen tab open **Track** with the ticket number and press **Yes, it's fixed**. | Closed. If the citizen says **No**, it reopens and goes back to the contractor. | "A repair only counts when the citizen confirms it." |
| **9. The money-saver** | **Upload documents** → Try **N5** (a paid "special repair" tender on km 5–7 of the same road). | Before saving, a **red warning** says this stretch is under guarantee. After saving, **Home** shows **"Stop payments — the contractor must repair these for free"**, and the **Budget plan** lists it under **Do not pay**. | "Pravi stops the department paying ₹8.75 lakh for a repair the contractor owes for free." |

**Tips**
- If a step's preview says something unexpected, check the "Which road or building" box. After step 1 it should show `Waghodia to Jarod Road km 0–12`.
- To redo the demo: **Settings → Reset demo data**, then start again from N1.
- **Real online PDFs work the same way.** Download a tender or work order from nprocure or the R&B website, upload it, choose **+ Create new asset** if it's a new road, and upload later documents with the same Tender ID.
- For stages with no public document (for example "Work in progress"), open the work on **Works & tenders** and press **Move to …**.

### Other sample documents (for the existing demo roads)
| File | Shows |
|---|---|
| `1_tender_Vadodara-Waghodia_special_repair.pdf` | A paid repair on a road still under guarantee → red alert |
| `2_work_order_…` | Its work order |
| `3_completion_Vadodara-Savli_widening.pdf` | Completes a delayed widening → guarantee starts |
| `4_tender_Padra-Karjan_resurfacing.pdf` | A legitimate resurfacing tender on an old road → no alert |

Regenerate all sample PDFs (dates relative to today): `python scripts/make_sample_docs.py`

## Part C — Hierarchy and the ideas from Mumbai (5 minutes)

| Step | What you do | What happens | What to say to the judges |
|---|---|---|---|
| **1. Chain of command** | Log in as **`ce_state` / `Chief@123`** → **Offices**. Click **Vadodara Circle**, then **Vadodara Division**. | A league table of the units below: open and late complaints, on-time repairs, drains cleaned, works waiting for approval, ₹ at risk. Other divisions show "not on Pravi yet". | "Each officer sees their own office and everything under it — the same way R&B is organised." |
| **2. Switch office** | In the sidebar **Viewing** box, pick **Padra Sub-division**. | Every page (map, assets, complaints, works) now shows only Padra. | "A Chief Engineer can look inside any sub-division in one click." |
| **3. Escalation** | **Complaints → Past deadline**. | Each late complaint says how late it is and who it has escalated to (Executive → Superintending → Chief Engineer). The CE's Home shows "Complaints escalated to you". | "Mumbai fixes monsoon potholes in 24 h and the Bombay High Court set 48 h. If a sub-division misses it, the complaint climbs the ladder by itself." |
| **4. Approval by cost** | Log in as **`de_vadodara`** → **Works** → the ₹3.8 lakh railing work → **Move to Approved** (allowed). Then as **`ee_vadodara`** open the ₹2.6 crore re-carpeting proposal. | The Deputy EE can approve up to ₹5 lakh; the EE sees "needs approval from the Chief Engineer". | "Files go to the right desk automatically — no one sits on a proposal they can't sanction." |
| **5. Road digging** | As **`ee_vadodara`** → **Road digging**. Note Gujarat Gas dug MDR-VW km 5.6–6.4 and has **not restored** it. Then **Complaints** → the "gas pipeline" crack → Check on site → Assign repair. | The complaint is assigned to **Gujarat Gas**, not the road contractor. | "Contractors often say 'someone dug my road'. Pravi records who dug where, so the right party pays." |
| **6. New digging request** | **New digging request** on the new Waghodia–Jarod road (after Part B), then **Check the rules**. | "Not allowed: first year of the guarantee." On an older road it is allowed, with a restoration charge; monsoon dates are blocked. | "Taken from Mumbai's trenching policy." |
| **7. Safety class** | **Roads & buildings → R&B Staff Quarters** → Log inspection → Structural audit → class **C1**. | The building becomes **Urgent — close / evacuate**. | "Mumbai's C1–C3 classes turn an audit report into an action." |
| **8. Public scorecard** | Open **`/performance`** (no login). | Each sub-division's on-time repairs, drains cleaned before the monsoon, bridges inspected and dug roads not restored. | "Citizens can see how their taluka's office is doing." |

