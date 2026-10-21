@echo off
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
)
echo.
echo Cac may khac trong mang truy cap bang mot trong cac dia chi IPv4 sau, cong 8000:
ipconfig | findstr /C:"IPv4"
echo.
.venv\Scripts\python -X utf8 -m uvicorn backend.app:app --host 0.0.0.0 --port 8000
