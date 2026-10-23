@echo off
cd /d %~dp0
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
)
start "" http://127.0.0.1:8000
.venv\Scripts\python -X utf8 -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
