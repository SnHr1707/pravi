@echo off
REM Windows: double-click or run from a terminal in this folder
if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
pip install -r requirements.txt
echo.
echo Open http://localhost:8000  (staff login: ee_vadodara / Exec@123)
python -m uvicorn app.main:app --port 8000
